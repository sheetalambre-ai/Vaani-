"""Remove known walkthrough records without touching real meeting data."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, delete, update
from app import models


async def purge_known_demo_data(db: AsyncSession):
    """Purge only app walkthroughs and the synthetic latency drafts used in QA."""
    walkthrough_titles = {
        "Product planning — demo",
        "Latency benchmark — private draft",
        "Latency verification — private draft",
        "Latency check — private draft — 2026-11-01",
        "Provider verification — private draft — 2026-11-01",
    }
    # Exact transcripts used for synthetic production checks. Match the raw
    # text too, in case a deployment normalized the title differently.
    qa_transcripts = {
        "Alex: We decided to set launch pricing at $49 per month instead of $29, effective November 15. Jordan: I will update the pricing page by November 10. Alex: We are moving the mobile launch from Q1 to November 20, 2026.",
        "Ari: We decided to retain the $39 monthly price for the winter launch. Morgan: I will update the pricing page by November 12, 2026. Ari: The beta will now open on December 4, 2026, replacing the earlier January plan.",
        "Nina: We decided the support team will own the November onboarding launch. Omar: I will publish the onboarding checklist by November 14, 2026. Nina: We are moving the launch to November 21, replacing the previous December 5 date.",
    }
    result = await db.execute(
        select(models.Meeting).where(
            or_(
                models.Meeting.raw_input == "[seeded]",
                models.Meeting.raw_input.in_(qa_transcripts),
                models.Meeting.title.in_(walkthrough_titles),
            )
        )
    )
    meetings = list(result.scalars().unique().all())
    if not meetings:
        return

    meeting_ids = [meeting.id for meeting in meetings]
    decision_rows = await db.execute(
        select(models.Decision.id).where(models.Decision.meeting_id.in_(meeting_ids))
    )
    decision_ids = [row[0] for row in decision_rows.all()]
    if decision_ids:
        conflicting_rows = await db.execute(
            select(models.Conflict).where(
                or_(
                    models.Conflict.new_decision_id.in_(decision_ids),
                    models.Conflict.old_decision_id.in_(decision_ids),
                )
            )
        )
        conflicts = list(conflicting_rows.scalars().all())
        affected_real_decisions = {
            conflict.new_decision_id
            for conflict in conflicts
            if conflict.new_decision_id not in decision_ids
        }
        await db.execute(
            delete(models.Conflict).where(
                or_(
                    models.Conflict.new_decision_id.in_(decision_ids),
                    models.Conflict.old_decision_id.in_(decision_ids),
                )
            )
        )
        if affected_real_decisions:
            still_conflicted_rows = await db.execute(
                select(models.Conflict.new_decision_id).where(
                    models.Conflict.new_decision_id.in_(affected_real_decisions),
                    models.Conflict.resolution == "open",
                )
            )
            still_conflicted = {row[0] for row in still_conflicted_rows.all()}
            resolved_ids = affected_real_decisions - still_conflicted
            if resolved_ids:
                await db.execute(
                    update(models.Decision)
                    .where(models.Decision.id.in_(resolved_ids), models.Decision.status == "conflicted")
                    .values(status="active")
                )
    for meeting in meetings:
        await db.delete(meeting)
    await db.commit()
    print(f"[cleanup] Removed {len(meetings)} known demo/QA meetings.")
