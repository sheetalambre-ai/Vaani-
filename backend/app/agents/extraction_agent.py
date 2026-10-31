"""ExtractionAgent: extracts decisions, action items and self-corrections from cleaned transcript."""
from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional
from app.llm_router import chat_json


class DecisionExtract(BaseModel):
    statement: str
    rationale: Optional[str] = None
    alternatives_rejected: Optional[list[str]] = None
    decided_by: Optional[str] = None
    evidence_quote: str


class ActionItemExtract(BaseModel):
    task: str
    owner: Optional[str] = None
    due_date: Optional[str] = None  # ISO date string or null
    done_definition: Optional[str] = None
    evidence_quote: str
    missing_fields: list[str] = Field(default_factory=list)


class SelfCorrection(BaseModel):
    field: str
    original_value: str
    corrected_value: str
    evidence_quote: str


class ExtractionResult(BaseModel):
    decisions: list[DecisionExtract] = Field(default_factory=list)
    action_items: list[ActionItemExtract] = Field(default_factory=list)
    self_corrections: list[SelfCorrection] = Field(default_factory=list)


SYSTEM_PROMPT = """You are an expert meeting analyst. Extract structured data from the meeting transcript.

Rules:
- Quote evidence VERBATIM from the transcript (evidence_quote field).
- NEVER invent an owner or date — return null if not mentioned.
- Resolve relative dates (Thursday, next Friday) against the meeting_date provided.
- When someone self-corrects ("Thursday, no wait, Friday"), keep the FINAL value, log the original in self_corrections.
- List missing_fields on each action_item (e.g. ["owner"] or ["due_date"] or []).
- Return ONLY valid JSON matching this schema exactly.

Schema:
{
  "decisions": [{"statement": "...", "rationale": "...", "alternatives_rejected": [], "decided_by": "...", "evidence_quote": "..."}],
  "action_items": [{"task": "...", "owner": "...", "due_date": "YYYY-MM-DD or null", "done_definition": "...", "evidence_quote": "...", "missing_fields": []}],
  "self_corrections": [{"field": "due_date", "original_value": "Thursday", "corrected_value": "Friday", "evidence_quote": "..."}]
}"""


async def extract(cleaned_transcript: str, meeting_date: date) -> ExtractionResult:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Meeting date: {meeting_date.isoformat()}\n\nTranscript:\n{cleaned_transcript}"},
    ]
    raw = await chat_json(messages)

    # Validate with Pydantic
    return ExtractionResult(
        decisions=[DecisionExtract(**d) for d in raw.get("decisions", [])],
        action_items=[ActionItemExtract(**a) for a in raw.get("action_items", [])],
        self_corrections=[SelfCorrection(**s) for s in raw.get("self_corrections", [])],
    )
