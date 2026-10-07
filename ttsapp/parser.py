"""Parsing of the simple ``Speaker: text`` conversation script format."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class ConversationLine:
    """One parsed line of dialogue ready for speech synthesis."""

    index: int
    speaker: str
    text: str
    voice: str


class UnknownSpeakerError(ValueError):
    """Raised when a speaker in the script has no configured voice."""


def parse_conversation(input_file: Path, voices: Dict[str, str]) -> List[ConversationLine]:
    """Read ``input_file`` and return the ordered list of dialogue lines.

    Each non-blank line must be formatted as ``Speaker: text``. ``voices``
    maps each expected speaker label to an Edge TTS voice name.
    """

    lines: List[ConversationLine] = []

    with open(input_file, "r", encoding="utf-8") as file:
        for raw_line in file:
            raw_line = raw_line.strip()

            if not raw_line:
                continue

            if ":" not in raw_line:
                raise ValueError(
                    f"Malformed line (expected 'Speaker: text'): {raw_line!r}"
                )

            speaker, text = raw_line.split(":", 1)
            speaker = speaker.strip()
            text = text.strip()

            if speaker not in voices:
                raise UnknownSpeakerError(
                    f"Unknown speaker '{speaker}'. Expected: {list(voices.keys())}"
                )

            lines.append(
                ConversationLine(
                    index=len(lines) + 1,
                    speaker=speaker,
                    text=text,
                    voice=voices[speaker],
                )
            )

    return lines
