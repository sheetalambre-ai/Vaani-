"""DigestAgent: builds weekly per-person digests."""
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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

    # Decisions mentioning the person
    result = await db.execute(select(models.Decision))
    all_decisions = result.scalars().all()
    relevant_decisions = [d for d in all_decisions if person_name.lower() in (d.statement or "").lower() or person_name.lower() in (d.decided_by or "").lower()]

    # Open conflicts
    result2 = await db.execute(select(models.Conflict).where(models.Conflict.resolution == "open"))
    open_conflicts = result2.scalars().all()

    return {
        "person": person_name,
        "generated_at": now.isoformat(),
        "due_this_week": [_item_dict(i) for i in due_this_week],
        "overdue": [_item_dict(i) for i in overdue],
        "done": [_item_dict(i) for i in done],
        "relevant_decisions": [{"id": d.id, "statement": d.statement, "status": d.status} for d in relevant_decisions],
        "open_conflicts": len(open_conflicts),
    }


def _item_dict(item: models.ActionItem) -> dict:
    return {"id": item.id, "task": item.task, "due_date": item.due_date, "status": item.status}
