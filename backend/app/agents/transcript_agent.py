"""TranscriptAgent: parses dictated or pasted text into speaker-attributed utterances."""
import re
from pydantic import BaseModel


class Utterance(BaseModel):
    speaker: str
    text: str


FILLER_PATTERN = re.compile(
    r"\b(um+|uh+|er+|ah+|like,?\s+|you know,?\s+|so um|okay so|i mean,?\s+)\b", re.IGNORECASE
)
SPEAKER_LINE = re.compile(r"^([^:\n]{1,30}):\s+(.+)$")


def _strip_fillers(text: str) -> str:
    cleaned = FILLER_PATTERN.sub(" ", text)
    cleaned = re.sub(r" {2,}", " ", cleaned).strip()
    return cleaned


def parse_transcript(raw: str) -> tuple[list[Utterance], str]:
    """
    Returns (utterances, cleaned_transcript).
    Handles 'Speaker: text' format and plain dictation (single block → Unknown speaker).
    """
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    utterances: list[Utterance] = []

    # Accept numbered and Unicode speaker labels too (for example, Speaker 1
    # or Devanagari names), not only plain ASCII names.
    has_labels = any(SPEAKER_LINE.match(line) for line in lines)

    if has_labels:
        for line in lines:
            m = SPEAKER_LINE.match(line)
            if m:
                speaker = m.group(1).strip().title()
                text = _strip_fillers(m.group(2).strip())
                utterances.append(Utterance(speaker=speaker, text=text))
            else:
                # continuation or unlabeled
                if utterances:
                    utterances[-1] = Utterance(
                        speaker=utterances[-1].speaker,
                        text=utterances[-1].text + " " + _strip_fillers(line),
                    )
                else:
                    utterances.append(Utterance(speaker="Unknown", text=_strip_fillers(line)))
    else:
        # Plain dictation block — treat as one Unknown utterance
        full = " ".join(lines)
        cleaned = _strip_fillers(full)
        utterances.append(Utterance(speaker="Unknown", text=cleaned))

    cleaned_transcript = "\n".join(f"{u.speaker}: {u.text}" for u in utterances)
    return utterances, cleaned_transcript
