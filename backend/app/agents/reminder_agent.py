"""ReminderAgent: schedules T-24h and T-2h reminders."""
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app import repository, models


async def schedule_reminders(db: AsyncSession, item: models.ActionItem):
    """Create reminder records for T-24h and T-2h before due_date."""
    if not item.due_date:
        return
    try:
        due = datetime.fromisoformat(item.due_date)
    except ValueError:
        return

    for delta in [timedelta(hours=24), timedelta(hours=2)]:
        send_at = due - delta
        if send_at > datetime.utcnow():
            await repository.create_reminder(db, item.id, send_at)


async def reschedule_reminders(db: AsyncSession, item: models.ActionItem):
    await repository.delete_unsent_reminders(db, item.id)
    await schedule_reminders(db, item)


async def fire_due_reminders(db: AsyncSession, force: bool = False):
    """Fire all reminders that are due (used by scheduler and simulate-time)."""
    now = datetime.utcnow()
    reminders = await repository.get_unsent_reminders(db) if force else await repository.get_due_reminders(db, now)
    fired = []
    for r in reminders:
        await _send_reminder(db, r)
        await repository.mark_reminder_sent(db, r.id, now)
        fired.append(r.id)
    return fired


async def _send_reminder(db: AsyncSession, reminder: models.Reminder):
    item = await repository.get_action_item(db, reminder.action_item_id)
    message = f"Reminder: '{item.task}' (owner: {item.owner}) is due {item.due_date}"

    if reminder.channel == "telegram" and item.owner:
        person = await repository.get_person_by_name(db, item.owner)
        if person and person.telegram_chat_id and await _send_telegram(message, person.telegram_chat_id):
            return
    await repository.create_notification(db, message)


async def _send_telegram(message: str, chat_id: str) -> bool:
    from app.config import settings
    if not settings.TELEGRAM_BOT_TOKEN:
        return False
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": message},
        )
        response.raise_for_status()
    return True
