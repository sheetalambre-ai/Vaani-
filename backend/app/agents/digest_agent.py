"""DigestAgent: builds weekly per-person digests."""
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app import models, repository


async def build_digest(db: AsyncSession, person_name: str) -> dict:
    now = datetime.utcnow()
    week_end = now + timedelta(days=7)

    all_items = await repository.get_all_action_items(db)
    person_items = [a for a in all_items if a.owner and a.owner.lower() == person_name.lower()]

    due_this_week, overdue, done = [], [], []
    for item in person_items:
        if item.status == "done":
            done.append(item)
        elif item.due_date:
            try:
                due = datetime.fromisoformat(item.due_date)
                if due < now:
                    overdue.append(item)
                elif due <= week_end:
                    due_this_week.append(item)
            except ValueError:
                pass

    assigned_meeting_ids = {item.meeting_id for item in person_items}

    # Include decisions from meetings where the person owns work, plus decisions
    # that directly name them or identify them as the decision maker.
    all_decisions = await repository.get_all_decisions(db)
    relevant_decisions = [
        decision for decision in all_decisions
        if decision.meeting_id in assigned_meeting_ids
        or person_name.casefold() in (decision.statement or "").casefold()
        or person_name.casefold() in (decision.decided_by or "").casefold()
    ]

    # A conflict affects a person if it touches one of their assigned meetings
    # or either decision explicitly names them.
    open_conflict_items = []
    for conflict in await repository.get_open_conflicts(db):
        new_decision = await repository.get_decision(db, conflict.new_decision_id)
        old_decision = await repository.get_decision(db, conflict.old_decision_id)
        decisions = [d for d in (new_decision, old_decision) if d]
        affects_person = any(
            d.meeting_id in assigned_meeting_ids
            or person_name.casefold() in (d.statement or "").casefold()
            or person_name.casefold() in (d.decided_by or "").casefold()
            for d in decisions
        )
        if affects_person:
            open_conflict_items.append({
                "id": conflict.id,
                "type": conflict.type,
                "severity": conflict.severity,
                "explanation": conflict.explanation,
                "new_decision": new_decision.statement if new_decision else None,
                "old_decision": old_decision.statement if old_decision else None,
            })

    return {
        "person": person_name,
        "generated_at": now.isoformat(),
        "due_this_week": [_item_dict(i) for i in due_this_week],
        "overdue": [_item_dict(i) for i in overdue],
        "done": [_item_dict(i) for i in done],
        "relevant_decisions": [{"id": d.id, "statement": d.statement, "status": d.status} for d in relevant_decisions],
        "open_conflicts": len(open_conflict_items),
        "open_conflict_items": open_conflict_items,
    }


def _item_dict(item: models.ActionItem) -> dict:
    return {"id": item.id, "task": item.task, "due_date": item.due_date, "status": item.status}
