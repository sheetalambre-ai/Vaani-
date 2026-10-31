"""CorrectionAgent: converts spoken edits into field patches."""
from pydantic import BaseModel
from typing import Optional
from app.llm_router import chat_json


class CorrectionPatch(BaseModel):
    target_type: str  # decision | action_item
    target_id: Optional[int] = None  # null if agent can't identify
    field: str
    new_value: str
    confidence: str  # high|medium|low


SYSTEM_PROMPT = """You are a correction interpreter for meeting action items and decisions.

Given a spoken correction and the list of current items, identify what needs to change.

Respond with JSON:
{"target_type": "action_item|decision", "target_id": <id or null>, "field": "owner|due_date|task|statement", "new_value": "...", "confidence": "high|medium|low"}

If you cannot confidently identify the target, set target_id to null and confidence to low."""


async def parse_correction(spoken_text: str, action_items: list[dict], decisions: list[dict]) -> CorrectionPatch:
    items_summary = "\n".join(
        f"ActionItem id={a['id']}: task='{a['task']}' owner={a['owner']} due={a['due_date']}"
        for a in action_items
    )
    decisions_summary = "\n".join(
        f"Decision id={d['id']}: '{d['statement']}'"
        for d in decisions
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Spoken correction: \"{spoken_text}\"\n\nCurrent action items:\n{items_summary}\n\nCurrent decisions:\n{decisions_summary}"},
    ]
    raw = await chat_json(messages)
    return CorrectionPatch(**raw)
