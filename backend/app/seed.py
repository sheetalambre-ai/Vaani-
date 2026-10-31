"""Seed the DB with two past meetings on first run."""
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app import models, repository


DEMO_DICTATION = (
    "so um, okay, regarding pricing I think we should go with forty nine a month, yeah forty nine. "
    "And uh Priya will finish the pricing page by Thursday, no wait, Friday. "
    "Also let's ship the mobile app in November, Rahul can you own the app store submission, like by the 15th."
)


async def seed_if_empty(db: AsyncSession):
    result = await db.execute(select(func.count()).select_from(models.Meeting))
    count = result.scalar()
    if count and count > 0:
        return  # already seeded

    # Meeting 1 — Oct 20
    m1 = await repository.create_meeting(
        db, title="Pricing & Payments", held_at=datetime(2026, 10, 20), raw_input="[seeded]"
    )
    await repository.update_meeting_transcript(db, m1.id, "Team: Discussed pricing and payment stack.")

    d1 = await repository.create_decision(db, m1.id, {
        "statement": "Launch pricing at $29/month",
        "rationale": "Competitive with market",
        "evidence_quote": "Launch pricing at $29/month",
        "decided_by": "Team",
    })
    d2 = await repository.create_decision(db, m1.id, {
        "statement": "Use Stripe for payments",
        "evidence_quote": "Use Stripe for payments",
        "decided_by": "Team",
    })
    await repository.create_action_item(db, m1.id, {
        "task": "Build landing page",
        "owner": "Priya",
        "due_date": "2026-10-28",
        "done_definition": "Landing page live with pricing section",
        "evidence_quote": "Priya will build the landing page by Oct 28",
        "missing_fields": [],
    })

    # Meeting 2 — Oct 27
    m2 = await repository.create_meeting(
        db, title="Mobile & Roadmap", held_at=datetime(2026, 10, 27), raw_input="[seeded]"
    )
    await repository.update_meeting_transcript(db, m2.id, "Team: Discussed mobile timeline.")

    d3 = await repository.create_decision(db, m2.id, {
        "statement": "Mobile app delayed to Q1 next year",
        "evidence_quote": "Mobile app delayed to Q1 next year",
        "decided_by": "Team",
    })
    await repository.create_action_item(db, m2.id, {
        "task": "Write API documentation",
        "owner": "Rahul",
        "due_date": "2026-11-05",
        "done_definition": "API docs published",
        "evidence_quote": "Rahul to write API docs by Nov 5",
        "missing_fields": [],
    })

    # Ensure people exist
    for name in ["Priya", "Rahul"]:
        await repository.get_or_create_person(db, name)

    print("[seed] Seeded 2 meetings with decisions and action items.")


async def seed_demo_review(db: AsyncSession):
    """Create a ready-to-review demo meeting without requiring an LLM key."""
    title = "Product planning — demo"
    existing = await repository.get_meeting_by_title(db, title)
    if existing:
        return existing

    from app.agents import reminder_agent, transcript_agent

    held_at = datetime(2026, 10, 31, 10, 0)
    meeting = await repository.create_meeting(db, title, held_at, DEMO_DICTATION)
    utterances, cleaned = transcript_agent.parse_transcript(DEMO_DICTATION)
    await repository.update_meeting_transcript(db, meeting.id, cleaned)
    await repository.create_utterances(
        db,
        meeting.id,
        [{"speaker": utterance.speaker, "text": utterance.text} for utterance in utterances],
    )

    pricing = await repository.create_decision(db, meeting.id, {
        "statement": "Launch pricing at $49/month",
        "rationale": "The team selected the revised price during the meeting.",
        "evidence_quote": "we should go with forty nine a month",
        "decided_by": "Team",
        "alternatives_rejected": ["$29/month"],
    })
    mobile = await repository.create_decision(db, meeting.id, {
        "statement": "Ship the mobile app in November",
        "rationale": "The team moved the release into November.",
        "evidence_quote": "let's ship the mobile app in November",
        "decided_by": "Team",
    })

    old_decisions = await repository.get_meeting_decisions(db, 1)
    old_pricing = next(d for d in old_decisions if "pricing" in d.statement.lower())
    mobile_decisions = await repository.get_meeting_decisions(db, 2)
    old_mobile = next(d for d in mobile_decisions if "mobile" in d.statement.lower())
    await repository.create_conflict(db, {
        "new_decision_id": pricing.id,
        "old_decision_id": old_pricing.id,
        "type": "reversal",
        "severity": "high",
        "explanation": (
            'Pricing changed from "$29/month" on Oct 20 to "$49/month" on Oct 31. '
            "The new decision reverses the earlier launch price."
        ),
    })
    await repository.create_conflict(db, {
        "new_decision_id": mobile.id,
        "old_decision_id": old_mobile.id,
        "type": "deadline",
        "severity": "high",
        "explanation": (
            "The Oct 27 decision delayed the mobile app to Q1 next year; the Oct 31 meeting "
            "moves shipment to November."
        ),
    })
    await repository.update_decision_status(db, pricing.id, "conflicted")
    await repository.update_decision_status(db, mobile.id, "conflicted")

    priya = await repository.create_action_item(db, meeting.id, {
        "task": "Finish the pricing page",
        "owner": "Priya",
        "due_date": "2026-11-06",
        "done_definition": "Pricing page is complete with the $49/month price.",
        "evidence_quote": "Priya will finish the pricing page by Thursday, no wait, Friday",
        "missing_fields": [],
    })
    rahul = await repository.create_action_item(db, meeting.id, {
        "task": "Submit the app store listing",
        "owner": "Rahul",
        "due_date": "2026-11-15",
        "done_definition": "The mobile app submission is accepted in the app store portal.",
        "evidence_quote": "Rahul can you own the app store submission, like by the 15th",
        "missing_fields": [],
    })
    await reminder_agent.schedule_reminders(db, priya)
    await reminder_agent.schedule_reminders(db, rahul)
    for name in ["Priya", "Rahul"]:
        await repository.get_or_create_person(db, name)

    await repository.create_correction(db, {
        "meeting_id": meeting.id,
        "target_type": "auto_detected",
        "target_id": priya.id,
        "field": "due_date",
        "old_value": "Thursday",
        "new_value": "Friday",
        "spoken_text": "by Thursday, no wait, Friday",
    })
    return meeting
