"""Orchestrates the meeting ingestion pipeline."""
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app import repository
from app.agents import transcript_agent, extraction_agent, memory_agent, conflict_agent, reminder_agent


async def process_meeting(db: AsyncSession, raw_input: str, title: str = None, held_at: datetime = None) -> dict:
    held_at = held_at or datetime.utcnow()
    title = title or f"Meeting {held_at.strftime('%b %d %Y')}"

    # 1. Create meeting record
    meeting = await repository.create_meeting(db, title=title, held_at=held_at, raw_input=raw_input)

    # 2. TranscriptAgent
    utterances, cleaned = transcript_agent.parse_transcript(raw_input)
    await repository.update_meeting_transcript(db, meeting.id, cleaned)
    await repository.create_utterances(db, meeting.id, [{"speaker": u.speaker, "text": u.text} for u in utterances])

    # 3. ExtractionAgent
    extraction = await extraction_agent.extract(cleaned, held_at.date())

    # 4. Save decisions + embed + detect conflicts
    saved_decisions = []
    all_conflicts = []

    for dec in extraction.decisions:
        d = await repository.create_decision(db, meeting.id, dec.model_dump())
        embedding = await memory_agent.embed_text(d.statement)
        if embedding:
            await repository.update_decision_embedding(db, d.id, embedding)
            d.embedding = embedding

        # Retrieve similar past decisions (excluding this meeting)
        past = await repository.get_all_active_decisions(db)
        past = [p for p in past if p.id != d.id and p.meeting_id != meeting.id]
        similar = memory_agent.retrieve_similar(d.statement, embedding or [], past, top_n=5)

        # ConflictAgent
        for old_d in similar:
            old_meeting = await repository.get_meeting(db, old_d.meeting_id)
            conflict_result = await conflict_agent.detect_conflict(
                new_decision=d,
                past_decision=old_d,
                new_meeting_date=held_at.strftime("%b %d %Y"),
                past_meeting_date=old_meeting.held_at.strftime("%b %d %Y") if old_meeting else "unknown",
            )
            if conflict_result.has_conflict:
                c = await repository.create_conflict(db, {
                    "new_decision_id": d.id,
                    "old_decision_id": old_d.id,
                    "type": conflict_result.type,
                    "severity": conflict_result.severity,
                    "explanation": conflict_result.explanation,
                })
                await repository.update_decision_status(db, d.id, "conflicted")
                all_conflicts.append(c)

        saved_decisions.append(d)

    # 5. Save action items + schedule reminders
    saved_items = []
    for item_data in extraction.action_items:
        item = await repository.create_action_item(db, meeting.id, item_data.model_dump())
        await reminder_agent.schedule_reminders(db, item)
        if item.owner:
            await repository.get_or_create_person(db, item.owner)
        saved_items.append(item)

    # 6. Save self-corrections
    for sc in extraction.self_corrections:
        await repository.create_correction(db, {
            "meeting_id": meeting.id,
            "target_type": "auto_detected",
            "target_id": None,
            "field": sc.field,
            "old_value": sc.original_value,
            "new_value": sc.corrected_value,
            "spoken_text": sc.evidence_quote,
        })

    return await build_review_payload(db, meeting.id)


async def build_review_payload(db: AsyncSession, meeting_id: int) -> dict:
    from app import models

    meeting = await repository.get_meeting(db, meeting_id)

    # Utterances
    utterances = await repository.get_meeting_utterances(db, meeting_id)

    # Decisions
    decisions = await repository.get_meeting_decisions(db, meeting_id)

    # Action items
    items = await repository.get_meeting_action_items(db, meeting_id)

    # Conflicts for this meeting
    conflicts = await repository.get_meeting_conflicts(db, meeting_id)
    decision_ids = {d.id for d in decisions}
    for conflict in conflicts:
        if conflict.old_decision_id not in decision_ids:
            old_decision = await repository.get_decision(db, conflict.old_decision_id)
            if old_decision:
                decisions.append(old_decision)
                decision_ids.add(old_decision.id)

    # Corrections
    corrections = await repository.get_meeting_corrections(db, meeting_id)

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
        "decisions": [decision_dict(d) for d in decisions],
        "action_items": [item_dict(a) for a in items],
        "conflicts": [conflict_dict(c) for c in conflicts],
        "corrections": [
            {"field": c.field, "old_value": c.old_value, "new_value": c.new_value, "spoken_text": c.spoken_text}
            for c in corrections
        ],
    }
