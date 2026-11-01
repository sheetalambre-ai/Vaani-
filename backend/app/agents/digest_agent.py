"""DigestAgent: builds weekly per-person digests."""
from datetime import datetime, timedelta
from sqlalchemy import select, func, or_
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession
from app import models, repository


async def build_digest(db: AsyncSession, person_name: str) -> dict:
    now = datetime.utcnow()
    week_end = now + timedelta(days=7)

    item_rows = await db.execute(
        select(models.ActionItem).where(func.lower(models.ActionItem.owner) == person_name.lower())
    )
    person_items = list(item_rows.scalars().all())

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
    decision_filters = [
        models.Decision.statement.ilike(f"%{person_name}%"),
        models.Decision.decided_by.ilike(f"%{person_name}%"),
    ]
    if assigned_meeting_ids:
        decision_filters.append(models.Decision.meeting_id.in_(assigned_meeting_ids))
    decision_rows = await db.execute(select(models.Decision).where(or_(*decision_filters)))
    relevant_decisions = list(decision_rows.scalars().all())

    # A conflict affects a person if it touches one of their assigned meetings
    # or either decision explicitly names them.
    open_conflict_items = []
    new_decision = aliased(models.Decision)
    old_decision = aliased(models.Decision)
    conflict_rows = await db.execute(
        select(models.Conflict, new_decision, old_decision)
        .join(new_decision, models.Conflict.new_decision_id == new_decision.id)
        .join(old_decision, models.Conflict.old_decision_id == old_decision.id)
        .where(models.Conflict.resolution == "open")
    )
    for conflict, new_item, old_item in conflict_rows.all():
        decisions = [new_item, old_item]
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
                "new_decision": new_item.statement,
                "old_decision": old_item.statement,
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
