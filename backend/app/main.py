from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

from app.database import init_db, get_db
from app.provider_http import provider_http_session
from app.seed import purge_known_demo_data
from app import models, repository
from app.pipeline import process_meeting, build_review_payload
from app.agents import correction_agent, executor_agent, reminder_agent, digest_agent, memory_agent

scheduler = AsyncIOScheduler(timezone="UTC")


async def _scheduled_reminders():
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await reminder_agent.fire_due_reminders(db)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await purge_known_demo_data(db)
    if not os.getenv("VERCEL"):
        scheduler.add_job(_scheduled_reminders, "interval", minutes=1, id="reminders", replace_existing=True)
        scheduler.start()
    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Vaaniमंथन", lifespan=lifespan)


@app.middleware("http")
async def strip_vercel_api_prefix(request: Request, call_next):
    path = request.scope.get("path", "")
    if path.startswith("/api/"):
        request.scope["path"] = path[4:]
        raw_path = request.scope.get("raw_path")
        if raw_path:
            request.scope["raw_path"] = raw_path[4:]
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Schemas ---

class MeetingCreate(BaseModel):
    text: str
    title: Optional[str] = None
    held_at: Optional[str] = None  # ISO datetime string


class ItemPatch(BaseModel):
    task: Optional[str] = None
    owner: Optional[str] = None
    due_date: Optional[str] = None
    done_definition: Optional[str] = None


class CorrectionCreate(BaseModel):
    spoken_text: str


class ConflictResolve(BaseModel):
    resolution: str  # accepted_new | kept_old


# --- Routes ---

@app.post("/meetings")
async def create_meeting(body: MeetingCreate, db: AsyncSession = Depends(get_db)):
    held_at = datetime.fromisoformat(body.held_at) if body.held_at else datetime.utcnow()
    try:
        async with provider_http_session():
            payload = await process_meeting(db, raw_input=body.text, title=body.title, held_at=held_at)
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/meetings/{meeting_id}/review")
async def review_meeting(meeting_id: int, db: AsyncSession = Depends(get_db)):
    meeting = await repository.get_meeting(db, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return await build_review_payload(db, meeting_id)


@app.post("/items/{item_id}/approve")
async def approve_item(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await repository.get_action_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await repository.update_action_item(db, item_id, {"status": "approved"})
    return {"id": item_id, "status": "approved"}


@app.post("/items/{item_id}/reject")
async def reject_item(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await repository.get_action_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await repository.update_action_item(db, item_id, {"status": "rejected"})
    return {"id": item_id, "status": "rejected"}


@app.post("/items/{item_id}/complete")
async def complete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await repository.get_action_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != "created":
        raise HTTPException(status_code=400, detail="Only tracker-created items can be marked complete")
    await repository.update_action_item(db, item_id, {"status": "done"})
    return {"id": item_id, "status": "done"}


@app.post("/items/{item_id}/publish")
async def publish_item(item_id: int, db: AsyncSession = Depends(get_db)):
    """Publish one explicitly approved task to the configured tracker."""
    item = await repository.get_action_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != "approved":
        raise HTTPException(status_code=400, detail="Only approved items can be published")
    try:
        external_ref = await executor_agent.create_task(item)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Tracker publish failed: {exc}") from exc
    await repository.update_action_item(db, item_id, {"status": "created", "external_ref": external_ref})
    return {"id": item_id, "status": "created", "external_ref": external_ref}


@app.patch("/items/{item_id}")
async def patch_item(item_id: int, body: ItemPatch, db: AsyncSession = Depends(get_db)):
    item = await repository.get_action_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        owner = updates.get("owner", item.owner)
        due_date = updates.get("due_date", item.due_date)
        missing_fields = []
        if not owner:
            missing_fields.append("owner")
        if not due_date:
            missing_fields.append("due_date")
        updates["missing_fields"] = missing_fields
        await repository.update_action_item(db, item_id, updates)
        if "due_date" in updates:
            updated_item = await repository.get_action_item(db, item_id)
            await reminder_agent.reschedule_reminders(db, updated_item)
    return {"id": item_id, "updated": updates}


@app.post("/meetings/{meeting_id}/correct")
async def correct_meeting(meeting_id: int, body: CorrectionCreate, db: AsyncSession = Depends(get_db)):
    meeting = await repository.get_meeting(db, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    items = await repository.get_meeting_action_items(db, meeting_id)
    decisions = await repository.get_meeting_decisions(db, meeting_id)

    patch = await correction_agent.parse_correction(
        body.spoken_text,
        [{"id": i.id, "task": i.task, "owner": i.owner, "due_date": i.due_date} for i in items],
        [{"id": d.id, "statement": d.statement} for d in decisions],
    )

    old_value = None
    target_found = False
    if patch.confidence == "low" or patch.target_id is None:
        raise HTTPException(status_code=422, detail="Could not confidently match that correction to an item")

    if patch.target_id:
        if patch.target_type == "action_item":
            if patch.field not in {"task", "owner", "due_date", "done_definition"}:
                raise HTTPException(status_code=422, detail="Unsupported action item field")
            item = await repository.get_action_item(db, patch.target_id)
            if item and item.meeting_id == meeting_id:
                target_found = True
                old_value = getattr(item, patch.field, None)
                await repository.update_action_item(db, patch.target_id, {patch.field: patch.new_value})
                if patch.field == "due_date":
                    updated_item = await repository.get_action_item(db, patch.target_id)
                    await reminder_agent.reschedule_reminders(db, updated_item)
        elif patch.target_type == "decision":
            if patch.field not in {"statement", "rationale"}:
                raise HTTPException(status_code=422, detail="Unsupported decision field")
            decision = await repository.get_decision(db, patch.target_id)
            if decision and decision.meeting_id == meeting_id:
                target_found = True
                old_value = getattr(decision, patch.field, None)
                updates = {patch.field: patch.new_value}
                if patch.field == "statement":
                    embeddings = await memory_agent.embed_texts([patch.new_value])
                    updates["embedding"] = embeddings[0] if embeddings else []
                await repository.update_decision(db, patch.target_id, updates)

    if not target_found:
        raise HTTPException(status_code=422, detail="Could not confidently match that correction to an item")

    await repository.create_correction(db, {
        "meeting_id": meeting_id,
        "target_type": patch.target_type,
        "target_id": patch.target_id,
        "field": patch.field,
        "old_value": str(old_value) if old_value is not None else None,
        "new_value": patch.new_value,
        "spoken_text": body.spoken_text,
    })

    return {"patch": patch.model_dump(), "old_value": old_value, "new_value": patch.new_value}


@app.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: int, body: ConflictResolve, db: AsyncSession = Depends(get_db)):
    conflict = await repository.get_conflict(db, conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    if body.resolution not in ("accepted_new", "kept_old"):
        raise HTTPException(status_code=400, detail="resolution must be accepted_new or kept_old")
    await repository.resolve_conflict(db, conflict_id, body.resolution)
    if body.resolution == "accepted_new":
        await repository.update_decision_status(db, conflict.old_decision_id, "superseded")
        await repository.update_decision_status(db, conflict.new_decision_id, "active")
    else:
        await repository.update_decision_status(db, conflict.new_decision_id, "superseded")
    return {"id": conflict_id, "resolution": body.resolution}


@app.post("/meetings/{meeting_id}/publish")
async def publish_meeting(meeting_id: int, db: AsyncSession = Depends(get_db)):
    meeting = await repository.get_meeting(db, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    items = await repository.get_meeting_action_items(db, meeting_id)
    approved = [i for i in items if i.status == "approved"]

    if not approved:
        raise HTTPException(status_code=400, detail="No approved items to publish")

    results = []
    for item in approved:
        try:
            ref = await executor_agent.create_task(item)
            await repository.update_action_item(db, item.id, {"status": "created", "external_ref": ref})
            results.append({"id": item.id, "task": item.task, "external_ref": ref, "status": "created"})
        except Exception as e:
            results.append({"id": item.id, "task": item.task, "error": str(e)})

    return {"published": results}


@app.get("/board")
async def get_board(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(models.ActionItem, models.Meeting.title)
        .join(models.Meeting, models.Meeting.id == models.ActionItem.meeting_id)
        .order_by(models.ActionItem.due_date.asc().nullslast(), models.ActionItem.id.desc())
    )
    board = {}
    for item, meeting_title in rows.all():
        board.setdefault(item.status, []).append({
            "id": item.id, "task": item.task, "owner": item.owner,
            "due_date": item.due_date, "status": item.status, "external_ref": item.external_ref,
            "meeting_id": item.meeting_id, "meeting_title": meeting_title,
        })
    return board


@app.get("/digest/{person}")
async def get_digest(person: str, db: AsyncSession = Depends(get_db)):
    return await digest_agent.build_digest(db, person)


@app.post("/digest/{person}/send")
async def send_digest(person: str, db: AsyncSession = Depends(get_db)):
    digest = await digest_agent.build_digest(db, person)
    msg = f"Weekly digest for {person}: {len(digest['due_this_week'])} due, {len(digest['overdue'])} overdue."
    await repository.create_notification(db, msg)
    recipient = await repository.get_person_by_name(db, person)
    if recipient and recipient.telegram_chat_id:
        from app.agents.reminder_agent import _send_telegram
        try:
            await _send_telegram(msg, recipient.telegram_chat_id)
        except Exception:
            # Keep the in-app digest available if Telegram is temporarily unreachable.
            pass
    return {"sent": True, "digest": digest}


@app.get("/notifications")
async def get_notifications(db: AsyncSession = Depends(get_db)):
    notes = await repository.get_notifications(db)
    return [{"id": n.id, "message": n.message, "created_at": n.created_at.isoformat(), "read": n.read} for n in notes]


@app.get("/cron/reminders", include_in_schema=False)
async def run_reminder_cron(request: Request, db: AsyncSession = Depends(get_db)):
    from app.config import settings
    if not settings.CRON_SECRET:
        raise HTTPException(status_code=503, detail="CRON_SECRET is not configured")
    if request.headers.get("authorization") != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    fired = await reminder_agent.fire_due_reminders(db)
    return {"fired_reminder_ids": fired}
