"""Orchestrates the meeting ingestion pipeline."""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app import models, repository
from app.agents import transcript_agent, extraction_agent, memory_agent, conflict_agent


async def process_meeting(db: AsyncSession, raw_input: str, title: str = None, held_at: datetime = None) -> dict:
    held_at = held_at or datetime.utcnow()
    title = title or f"Meeting {held_at.strftime('%b %d %Y')}"

    # Persist the raw meeting before calling external services, as before.
    meeting = models.Meeting(title=title, held_at=held_at, raw_input=raw_input)
    db.add(meeting)
    await db.flush()
    utterances, cleaned = transcript_agent.parse_transcript(raw_input)
    meeting.cleaned_transcript = cleaned
    utterance_rows = [
        models.Utterance(meeting_id=meeting.id, speaker=u.speaker, text=u.text)
        for u in utterances
    ]
    db.add_all(utterance_rows)
    await db.commit()

    # 1. Extract structured meeting data.
    extraction = await extraction_agent.extract(cleaned, held_at.date())

    # 2. Compare against a single snapshot of cross-meeting memory. Gemini's
    # batch endpoint embeds every new decision with one network round trip.
    # Embedding and reading prior decisions are independent. Overlap the
    # provider round trip with the DB query so the request pays only for the
    # slower of the two instead of their combined latency.
    new_embeddings, past_decisions = await asyncio.gather(
        memory_agent.embed_texts(
            [decision.statement for decision in extraction.decisions]
        ),
        repository.get_all_active_decisions(db),
    )
    past_decisions = [item for item in past_decisions if item.meeting_id != meeting.id]

    decisions = []
    for extracted, embedding in zip(extraction.decisions, new_embeddings):
        values = extracted.model_dump()
        decisions.append(models.Decision(
            meeting_id=meeting.id,
            statement=values["statement"],
            rationale=values.get("rationale"),
            alternatives_rejected=values.get("alternatives_rejected"),
            decided_by=values.get("decided_by"),
            evidence_quote=values.get("evidence_quote"),
            status="active",
            embedding=embedding or None,
        ))
    db.add_all(decisions)
    await db.flush()

    comparisons = []
    old_decisions_by_new_id = {}
    for decision in decisions:
        similar = memory_agent.retrieve_similar(
            decision.statement, decision.embedding or [], past_decisions, top_n=5
        )
        old_decisions_by_new_id[decision.id] = similar
        for old_decision in similar:
            comparisons.append((decision, old_decision))

    old_meeting_ids = {old.meeting_id for _, old in comparisons}
    old_meetings = {}
    if old_meeting_ids:
        rows = await db.execute(
            select(models.Meeting).where(models.Meeting.id.in_(old_meeting_ids))
        )
        old_meetings = {item.id: item for item in rows.scalars().all()}

    # Persist extracted decisions and release the database connection while
    # the conflict model evaluates the batch.
    await db.commit()

    dated_pairs = [
        (
            new,
            old,
            held_at.strftime("%b %d %Y"),
            old_meetings[old.meeting_id].held_at.strftime("%b %d %Y")
            if old.meeting_id in old_meetings else "unknown",
        )
        for new, old in comparisons
    ]
    outcomes = await conflict_agent.detect_conflicts_batch(dated_pairs)
    conflicts = []
    for (new_decision, old_decision), outcome in zip(comparisons, outcomes):
        if not outcome.has_conflict:
            continue
        new_decision.status = "conflicted"
        conflicts.append(models.Conflict(
            new_decision_id=new_decision.id,
            old_decision_id=old_decision.id,
            type=outcome.type,
            severity=outcome.severity,
            explanation=outcome.explanation,
            resolution="open",
        ))
    db.add_all(conflicts)

    # 3. Save all extracted entities in one transaction. Flush once to assign
    # action IDs, then add reminders and newly seen people before one commit.
    items = [models.ActionItem(
        meeting_id=meeting.id,
        task=item.task,
        owner=item.owner,
        due_date=item.due_date,
        done_definition=item.done_definition,
        evidence_quote=item.evidence_quote,
        missing_fields=item.missing_fields,
        status="pending_review",
    ) for item in extraction.action_items]
    db.add_all(items)
    await db.flush()

    reminders = []
    now = datetime.utcnow()
    for item in items:
        if not item.due_date:
            continue
        try:
            due = datetime.fromisoformat(item.due_date)
        except ValueError:
            continue
        reminders.extend(
            models.Reminder(action_item_id=item.id, send_at=due - delta, channel="in_app")
            for delta in (timedelta(hours=24), timedelta(hours=2))
            if due - delta > now
        )
    db.add_all(reminders)

    owner_names = {item.owner for item in items if item.owner}
    if owner_names:
        existing = await db.execute(select(models.Person).where(models.Person.name.in_(owner_names)))
        existing_names = {person.name for person in existing.scalars().all()}
        db.add_all(
            models.Person(name=name)
            for name in owner_names - existing_names
        )

    corrections = [models.Correction(
        meeting_id=meeting.id,
        target_type="auto_detected",
        target_id=None,
        field=item.field,
        old_value=item.original_value,
        new_value=item.corrected_value,
        spoken_text=item.evidence_quote,
    ) for item in extraction.self_corrections]
    db.add_all(corrections)
    await db.commit()

    conflicting_old_ids = {item.old_decision_id for item in conflicts}
    related_decisions = {
        old.id: old
        for past in old_decisions_by_new_id.values()
        for old in past
        if old.id in conflicting_old_ids
    }
    return serialize_review_payload(
        meeting, utterance_rows, decisions, items, conflicts, corrections,
        list(related_decisions.values()),
    )


async def build_review_payload(db: AsyncSession, meeting_id: int) -> dict:
    meeting = await repository.get_meeting(db, meeting_id)

    # Utterances
    utterances = await repository.get_meeting_utterances(db, meeting_id)

    # Decisions
    decisions = await repository.get_meeting_decisions(db, meeting_id)

    # Action items
    items = await repository.get_meeting_action_items(db, meeting_id)

    # Conflicts for this meeting
    conflicts = await repository.get_meeting_conflicts(db, meeting_id)
    old_ids = {c.old_decision_id for c in conflicts} - {d.id for d in decisions}
    if old_ids:
        rows = await db.execute(select(models.Decision).where(models.Decision.id.in_(old_ids)))
        decisions.extend(rows.scalars().all())

    # Corrections
    corrections = await repository.get_meeting_corrections(db, meeting_id)

    return serialize_review_payload(meeting, utterances, decisions, items, conflicts, corrections)


def serialize_review_payload(meeting, utterances, decisions, items, conflicts, corrections, related_decisions=None) -> dict:
    """Serialize an already-loaded review without additional database reads."""
    meeting_id = meeting.id
    decision_by_id = {d.id: d for d in decisions}
    decision_by_id.update({d.id: d for d in related_decisions or []})
    visible_decisions = list(decision_by_id.values())

    def decision_dict(d: models.Decision):
        return {
            "id": d.id, "statement": d.statement, "rationale": d.rationale,
            "decided_by": d.decided_by, "evidence_quote": d.evidence_quote,
            "status": d.status, "alternatives_rejected": d.alternatives_rejected,
        }

    def item_dict(a: models.ActionItem):
        return {
            "id": a.id, "task": a.task, "owner": a.owner, "due_date": a.due_date,
            "done_definition": a.done_definition, "evidence_quote": a.evidence_quote,
            "missing_fields": a.missing_fields or [], "status": a.status,
        }

    def conflict_dict(c: models.Conflict):
        return {
            "id": c.id, "new_decision_id": c.new_decision_id, "old_decision_id": c.old_decision_id,
            "type": c.type, "severity": c.severity, "explanation": c.explanation, "resolution": c.resolution,
        }

    return {
        "meeting_id": meeting_id,
        "title": meeting.title,
        "held_at": meeting.held_at.isoformat(),
        "raw_input": meeting.raw_input,
        "cleaned_transcript": meeting.cleaned_transcript,
        "utterances": [{"speaker": u.speaker, "text": u.text} for u in utterances],
        "decisions": [decision_dict(d) for d in visible_decisions],
        "action_items": [item_dict(a) for a in items],
        "conflicts": [conflict_dict(c) for c in conflicts],
        "corrections": [
            {"field": c.field, "old_value": c.old_value, "new_value": c.new_value, "spoken_text": c.spoken_text}
            for c in corrections
        ],
    }
