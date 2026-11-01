"""ConflictAgent: compares new decisions against similar past ones and classifies conflicts."""
import asyncio
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


async def detect_conflicts_batch(
    pairs: list[tuple[models.Decision, models.Decision, str, str]],
) -> list[ConflictResult]:
    """Classify several independent decision pairs in one model request."""
    if not pairs:
        return []

    comparisons = []
    for index, (new_decision, past_decision, new_date, past_date) in enumerate(pairs):
        comparisons.append(
            f"COMPARISON {index}\n"
            f"NEW DECISION ({new_date}): {new_decision.statement}\n"
            f"NEW EVIDENCE: {new_decision.evidence_quote or ''}\n"
            f"PAST DECISION ({past_date}): {past_decision.statement}\n"
            f"PAST EVIDENCE: {past_decision.evidence_quote or ''}"
        )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT + """

You will receive multiple numbered comparisons. Assess each independently.
Return exactly one result for every comparison, using its index:
{"results":[{"candidate_index":0,"has_conflict":false,"type":null,"severity":null,"explanation":null}]}
Do not compare decisions across different comparison numbers. Cite both dates and evidence when a conflict exists.""",
        },
        {"role": "user", "content": "\n\n".join(comparisons)},
    ]
    try:
        raw = await chat_json(messages)
        results = raw.get("results") if isinstance(raw, dict) else None
        if not isinstance(results, list):
            raise ValueError("Conflict agent returned an invalid batch response")

        parsed: dict[int, ConflictResult] = {}
        for result in results:
            if not isinstance(result, dict):
                raise ValueError("Conflict agent returned an invalid comparison")
            index = result.get("candidate_index")
            if not isinstance(index, int) or index < 0 or index >= len(pairs) or index in parsed:
                raise ValueError("Conflict agent returned an invalid comparison index")
            parsed[index] = ConflictResult(**{
                key: value for key, value in result.items() if key != "candidate_index"
            })
        if len(parsed) != len(pairs):
            raise ValueError("Conflict agent omitted one or more comparisons")
        return [parsed[index] for index in range(len(pairs))]
    except (KeyError, TypeError, ValueError):
        # Keep the original per-pair path as a reliability fallback if a model
        # fails to honor the batch schema. Normal requests still use one call.
        return await asyncio.gather(*(
            detect_conflict(new, old, new_date, old_date)
            for new, old, new_date, old_date in pairs
        ))
