"""ConflictAgent: compares new decisions against similar past ones and classifies conflicts."""
from pydantic import BaseModel
from typing import Optional
from app.llm_router import chat_json
from app import models


class ConflictResult(BaseModel):
    has_conflict: bool
    type: Optional[str] = None  # reversal|deadline|scope|resource
    severity: Optional[str] = None  # low|medium|high
    explanation: Optional[str] = None


SYSTEM_PROMPT = """You are a conflict detection analyst for meeting decisions.

Compare the NEW decision with each PAST decision. Determine if there is a conflict.

Conflict types:
- reversal: new decision reverses or contradicts a past decision
- deadline: conflicting deadlines for the same item
- scope: scope has changed (expanded, reduced, or shifted)
- resource: same person/resource assigned to conflicting tasks

Respond with JSON only:
{"has_conflict": true/false, "type": "reversal|deadline|scope|resource|null", "severity": "low|medium|high|null", "explanation": "cite both evidence quotes and dates"}

Return has_conflict: false with null type/severity/explanation if there is no real conflict."""


async def detect_conflict(
    new_decision: models.Decision,
    past_decision: models.Decision,
    new_meeting_date: str,
    past_meeting_date: str,
) -> ConflictResult:
    user_content = f"""NEW DECISION (from {new_meeting_date}):
"{new_decision.statement}"
Evidence: "{new_decision.evidence_quote}"

PAST DECISION (from {past_meeting_date}):
"{past_decision.statement}"
Evidence: "{past_decision.evidence_quote}"

Is there a conflict?"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    raw = await chat_json(messages)
    return ConflictResult(**raw)
