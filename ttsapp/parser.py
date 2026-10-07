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

    with open(input_file, "r", encoding="utf-8") as file:
        return parse_conversation_text(file.read(), voices)


def parse_conversation_text(text: str, voices: Dict[str, str]) -> List[ConversationLine]:
    """Parse an in-memory conversation script (same format as ``parse_conversation``).

    Shared by the CLI (reading from a file) and the desktop UI (reading
    directly from a text input widget) so both go through identical
    validation.
    """

    lines: List[ConversationLine] = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        raw_line = raw_line.strip()

        if not raw_line:
            continue

        if ":" not in raw_line:
            raise ValueError(
                f"Malformed line (expected 'Speaker: text'): {raw_line!r}"
            )

        speaker, line_text = raw_line.split(":", 1)
        speaker = speaker.strip()
        line_text = line_text.strip()

        if not line_text:
            raise ValueError(
                f"Empty dialogue text on line {line_number} for speaker '{speaker}'."
            )

        if speaker not in voices:
            raise UnknownSpeakerError(
                f"Unknown speaker '{speaker}'. Expected: {list(voices.keys())}"
            )

        lines.append(
            ConversationLine(
                index=len(lines) + 1,
                speaker=speaker,
                text=line_text,
                voice=voices[speaker],
            )
        )

    return lines
