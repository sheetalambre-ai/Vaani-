import pytest
from fastapi import HTTPException

from app import repository
from app.agents import conflict_agent, memory_agent
from app.main import publish_meeting
from app.seed import seed_if_empty
from app.agents.extraction_agent import ActionItemExtract, DecisionExtract, ExtractionResult
from app.models import Decision


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
async def test_conflict_detection_on_seed_data(db_session, monkeypatch):
    await seed_if_empty(db_session)
    old_decisions = await repository.get_meeting_decisions(db_session, 1)
    old_price = next(d for d in old_decisions if "pricing" in d.statement.lower())
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
    await seed_if_empty(db_session)
    meeting = await repository.get_meeting(db_session, 1)
    with pytest.raises(HTTPException) as error:
        await publish_meeting(meeting.id, db_session)
    assert error.value.status_code == 400
    assert "approved" in error.value.detail.lower()
