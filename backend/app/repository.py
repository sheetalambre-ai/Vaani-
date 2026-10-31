"""Repository layer — all DB access goes through here so swapping SQLite → Supabase is isolated."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app import models
from datetime import datetime
from typing import Optional


# --- Meetings ---

async def create_meeting(db: AsyncSession, title: str, held_at: datetime, raw_input: str) -> models.Meeting:
    m = models.Meeting(title=title, held_at=held_at, raw_input=raw_input)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def get_meeting(db: AsyncSession, meeting_id: int) -> Optional[models.Meeting]:
    result = await db.execute(select(models.Meeting).where(models.Meeting.id == meeting_id))
    return result.scalar_one_or_none()


async def get_meeting_by_title(db: AsyncSession, title: str) -> Optional[models.Meeting]:
    result = await db.execute(select(models.Meeting).where(models.Meeting.title == title))
    return result.scalar_one_or_none()


async def update_meeting_transcript(db: AsyncSession, meeting_id: int, cleaned: str):
    await db.execute(update(models.Meeting).where(models.Meeting.id == meeting_id).values(cleaned_transcript=cleaned))
    await db.commit()


# --- Utterances ---

async def create_utterances(db: AsyncSession, meeting_id: int, utterances: list[dict]) -> list[models.Utterance]:
    objs = [models.Utterance(meeting_id=meeting_id, speaker=u["speaker"], text=u["text"]) for u in utterances]
    db.add_all(objs)
    await db.commit()
    return objs


# --- Decisions ---

async def create_decision(db: AsyncSession, meeting_id: int, data: dict) -> models.Decision:
    d = models.Decision(
        meeting_id=meeting_id,
        statement=data["statement"],
        rationale=data.get("rationale"),
        alternatives_rejected=data.get("alternatives_rejected"),
        decided_by=data.get("decided_by"),
        evidence_quote=data.get("evidence_quote"),
        status="active",
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def update_decision_embedding(db: AsyncSession, decision_id: int, embedding: list[float]):
    await db.execute(update(models.Decision).where(models.Decision.id == decision_id).values(embedding=embedding))
    await db.commit()


async def get_all_active_decisions(db: AsyncSession) -> list[models.Decision]:
    result = await db.execute(select(models.Decision).where(models.Decision.status.in_(["active", "conflicted"])))
    return list(result.scalars().all())


async def update_decision_status(db: AsyncSession, decision_id: int, status: str):
    await db.execute(update(models.Decision).where(models.Decision.id == decision_id).values(status=status))
    await db.commit()


async def update_decision(db: AsyncSession, decision_id: int, data: dict):
    await db.execute(update(models.Decision).where(models.Decision.id == decision_id).values(**data))
    await db.commit()


async def get_decision(db: AsyncSession, decision_id: int) -> Optional[models.Decision]:
    result = await db.execute(select(models.Decision).where(models.Decision.id == decision_id))
    return result.scalar_one_or_none()


# --- Action Items ---

async def create_action_item(db: AsyncSession, meeting_id: int, data: dict) -> models.ActionItem:
    a = models.ActionItem(
        meeting_id=meeting_id,
        task=data["task"],
        owner=data.get("owner"),
        due_date=data.get("due_date"),
        done_definition=data.get("done_definition"),
        evidence_quote=data.get("evidence_quote"),
        missing_fields=data.get("missing_fields", []),
        status="pending_review",
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


async def get_action_item(db: AsyncSession, item_id: int) -> Optional[models.ActionItem]:
    result = await db.execute(select(models.ActionItem).where(models.ActionItem.id == item_id))
    return result.scalar_one_or_none()


async def update_action_item(db: AsyncSession, item_id: int, data: dict):
    await db.execute(update(models.ActionItem).where(models.ActionItem.id == item_id).values(**data))
    await db.commit()


async def get_meeting_action_items(db: AsyncSession, meeting_id: int) -> list[models.ActionItem]:
    result = await db.execute(select(models.ActionItem).where(models.ActionItem.meeting_id == meeting_id))
    return list(result.scalars().all())


async def get_all_action_items(db: AsyncSession) -> list[models.ActionItem]:
    result = await db.execute(select(models.ActionItem))
    return list(result.scalars().all())


# --- Conflicts ---

async def create_conflict(db: AsyncSession, data: dict) -> models.Conflict:
    c = models.Conflict(
        new_decision_id=data["new_decision_id"],
        old_decision_id=data["old_decision_id"],
        type=data["type"],
        severity=data["severity"],
        explanation=data["explanation"],
        resolution="open",
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def get_conflict(db: AsyncSession, conflict_id: int) -> Optional[models.Conflict]:
    result = await db.execute(select(models.Conflict).where(models.Conflict.id == conflict_id))
    return result.scalar_one_or_none()


async def resolve_conflict(db: AsyncSession, conflict_id: int, resolution: str):
    await db.execute(update(models.Conflict).where(models.Conflict.id == conflict_id).values(resolution=resolution))
    await db.commit()


async def get_meeting_conflicts(db: AsyncSession, meeting_id: int) -> list[models.Conflict]:
    result = await db.execute(
        select(models.Conflict).join(models.Decision, models.Conflict.new_decision_id == models.Decision.id)
        .where(models.Decision.meeting_id == meeting_id)
    )
    return list(result.scalars().all())


# --- Corrections ---

async def create_correction(db: AsyncSession, data: dict) -> models.Correction:
    c = models.Correction(**data)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


# --- Reminders ---

async def create_reminder(db: AsyncSession, action_item_id: int, send_at: datetime, channel: str = "in_app") -> models.Reminder:
    r = models.Reminder(action_item_id=action_item_id, send_at=send_at, channel=channel)
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


async def get_due_reminders(db: AsyncSession, now: datetime) -> list[models.Reminder]:
    result = await db.execute(
        select(models.Reminder).where(models.Reminder.send_at <= now, models.Reminder.sent_at.is_(None))
    )
    return list(result.scalars().all())


async def get_unsent_reminders(db: AsyncSession) -> list[models.Reminder]:
    result = await db.execute(select(models.Reminder).where(models.Reminder.sent_at.is_(None)))
    return list(result.scalars().all())


async def delete_unsent_reminders(db: AsyncSession, action_item_id: int):
    await db.execute(
        models.Reminder.__table__.delete().where(
            models.Reminder.action_item_id == action_item_id,
            models.Reminder.sent_at.is_(None),
        )
    )
    await db.commit()


async def mark_reminder_sent(db: AsyncSession, reminder_id: int, sent_at: datetime):
    await db.execute(update(models.Reminder).where(models.Reminder.id == reminder_id).values(sent_at=sent_at))
    await db.commit()


# --- People ---

async def get_or_create_person(db: AsyncSession, name: str) -> models.Person:
    result = await db.execute(select(models.Person).where(models.Person.name == name))
    person = result.scalar_one_or_none()
    if not person:
        person = models.Person(name=name)
        db.add(person)
        await db.commit()
        await db.refresh(person)
    return person


async def get_all_people(db: AsyncSession) -> list[models.Person]:
    result = await db.execute(select(models.Person))
    return list(result.scalars().all())


async def get_person_by_name(db: AsyncSession, name: str) -> Optional[models.Person]:
    result = await db.execute(select(models.Person).where(models.Person.name.ilike(name)))
    return result.scalar_one_or_none()


# --- Notifications ---

async def create_notification(db: AsyncSession, message: str) -> models.Notification:
    n = models.Notification(message=message)
    db.add(n)
    await db.commit()
    await db.refresh(n)
    return n


async def get_notifications(db: AsyncSession) -> list[models.Notification]:
    result = await db.execute(select(models.Notification).order_by(models.Notification.created_at.desc()))
    return list(result.scalars().all())


async def get_meeting_decisions(db: AsyncSession, meeting_id: int) -> list[models.Decision]:
    result = await db.execute(select(models.Decision).where(models.Decision.meeting_id == meeting_id))
    return list(result.scalars().all())
