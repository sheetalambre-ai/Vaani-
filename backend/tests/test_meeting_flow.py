import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import repository
from app.agents import conflict_agent, memory_agent
from app.main import publish_meeting
from app.agents.extraction_agent import ActionItemExtract, DecisionExtract, ExtractionResult
from app.models import ActionItem, Conflict, Decision, Meeting, Reminder, Utterance
from app.seed import purge_known_demo_data
from datetime import datetime, timedelta
from app.agents.digest_agent import build_digest
from app.pipeline import build_review_payload


def test_extraction_schema_validity():
    result = ExtractionResult(
        decisions=[DecisionExtract(
            statement="Launch pricing at $49/month",
            evidence_quote="we should go with forty nine a month",
        )],
        action_items=[ActionItemExtract(
            task="Finish the pricing page",
            owner="Priya",
            due_date="2026-11-06",
            evidence_quote="Priya will finish the pricing page by Friday",
            missing_fields=[],
        )],
    )
    assert result.action_items[0].owner == "Priya"
    assert result.action_items[0].due_date == "2026-11-06"


@pytest.mark.asyncio
async def test_conflict_detection_against_stored_memory(db_session, monkeypatch):
    meeting = Meeting(title="Pricing review", held_at=datetime(2026, 10, 20), raw_input="Team: set launch price to $29/month.")
    db_session.add(meeting)
    await db_session.flush()
    old_price = Decision(
        meeting_id=meeting.id,
        statement="Launch pricing at $29/month",
        evidence_quote="set launch price to $29/month",
        status="active",
    )
    db_session.add(old_price)
    await db_session.commit()
    new_price = Decision(
        statement="Launch pricing at $49/month",
        evidence_quote="we should go with forty nine a month",
    )
    retrieved = memory_agent.retrieve_similar(
        new_price.statement,
        [],
        await repository.get_all_active_decisions(db_session),
        top_n=5,
    )
    assert old_price.id in {decision.id for decision in retrieved}

    async def classify(_messages):
        return {
            "has_conflict": True,
            "type": "reversal",
            "severity": "high",
            "explanation": 'The price changed from "$29/month" on Oct 20 to "$49/month" now.',
        }

    monkeypatch.setattr(conflict_agent, "chat_json", classify)
    outcome = await conflict_agent.detect_conflict(new_price, old_price, "Oct 31 2026", "Oct 20 2026")
    assert outcome.has_conflict is True
    assert outcome.type == "reversal"
    assert "Oct 20" in outcome.explanation


@pytest.mark.asyncio
async def test_publish_blocked_without_approval(db_session):
    meeting = Meeting(title="Unapproved meeting", held_at=datetime.utcnow(), raw_input="A team transcript.")
    db_session.add(meeting)
    await db_session.commit()
    with pytest.raises(HTTPException) as error:
        await publish_meeting(meeting.id, db_session)
    assert error.value.status_code == 400
    assert "approved" in error.value.detail.lower()


@pytest.mark.asyncio
async def test_demo_cleanup_preserves_real_meetings(db_session):
    seeded = Meeting(title="Pricing & Payments", held_at=datetime(2026, 10, 20), raw_input="[seeded]")
    real = Meeting(title="Pricing & Payments", held_at=datetime.utcnow(), raw_input="A real team's transcript.")
    demo = Meeting(title="Product planning — demo", held_at=datetime(2026, 10, 31), raw_input="walkthrough")
    db_session.add_all([seeded, real, demo])
    await db_session.flush()
    old_decision = Decision(meeting_id=real.id, statement="Earlier real decision", status="conflicted")
    seed_decision = Decision(meeting_id=seeded.id, statement="Seeded decision", status="active")
    demo_decision = Decision(meeting_id=demo.id, statement="Walkthrough decision", status="conflicted")
    task = ActionItem(meeting_id=demo.id, task="Walkthrough task", owner="Example", due_date="2026-11-05")
    utterance = Utterance(meeting_id=demo.id, speaker="Example", text="Walkthrough transcript")
    db_session.add_all([old_decision, seed_decision, demo_decision, task, utterance])
    await db_session.flush()
    db_session.add_all([
        Conflict(new_decision_id=demo_decision.id, old_decision_id=old_decision.id, type="scope", severity="low"),
        Conflict(new_decision_id=old_decision.id, old_decision_id=seed_decision.id, type="scope", severity="low"),
        Reminder(action_item_id=task.id, send_at=datetime(2026, 11, 4)),
    ])
    await db_session.commit()

    await purge_known_demo_data(db_session)

    assert await repository.get_meeting_by_title(db_session, "Product planning — demo") is None
    remaining = await db_session.execute(select(Meeting).where(Meeting.raw_input == "A real team's transcript."))
    assert remaining.scalar_one_or_none() is not None
    assert (await db_session.execute(select(Conflict))).scalars().all() == []
    assert (await db_session.execute(select(Reminder))).scalars().all() == []
    await db_session.refresh(old_decision)
    assert old_decision.status == "active"


@pytest.mark.asyncio
async def test_weekly_digest_keeps_tasks_and_conflicts(db_session):
    meeting = Meeting(title="Asha planning", held_at=datetime.utcnow(), raw_input="Asha will ship onboarding.")
    earlier = Meeting(title="Earlier planning", held_at=datetime.utcnow() - timedelta(days=2), raw_input="Earlier plan.")
    db_session.add_all([meeting, earlier])
    await db_session.flush()
    current_decision = Decision(meeting_id=meeting.id, statement="Asha will ship onboarding on Nov 20", decided_by="Asha")
    earlier_decision = Decision(meeting_id=earlier.id, statement="Onboarding was planned for December")
    task = ActionItem(
        meeting_id=meeting.id,
        task="Publish the onboarding checklist",
        owner="Asha",
        due_date=(datetime.utcnow() + timedelta(days=2)).date().isoformat(),
        status="created",
    )
    db_session.add_all([current_decision, earlier_decision, task])
    await db_session.flush()
    db_session.add(Conflict(
        new_decision_id=current_decision.id,
        old_decision_id=earlier_decision.id,
        type="deadline",
        severity="medium",
        explanation="The launch date moved earlier.",
        resolution="open",
    ))
    await db_session.commit()

    digest = await build_digest(db_session, "Asha")

    assert digest["due_this_week"][0]["task"] == "Publish the onboarding checklist"
    assert digest["open_conflicts"] == 1
    assert digest["open_conflict_items"][0]["old_decision"] == "Onboarding was planned for December"

    # A conflict belongs to both the new and earlier meeting in memory. Review
    # from either meeting should show the conflict and its counterpart decision.
    earlier_conflicts = await repository.get_meeting_conflicts(db_session, earlier.id)
    assert len(earlier_conflicts) == 1
    earlier_review = await build_review_payload(db_session, earlier.id)
    assert len(earlier_review["conflicts"]) == 1
    assert {d["statement"] for d in earlier_review["decisions"]} == {
        "Asha will ship onboarding on Nov 20",
        "Onboarding was planned for December",
    }
