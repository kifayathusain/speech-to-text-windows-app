"""Conservative text normalization and lossless provider-aware text segmentation."""

import math
import re
import unicodedata
from bisect import bisect_right
from dataclasses import dataclass

from .parser import ConversationLine

_SENTENCE_END = re.compile(
    r"""[.!?]+["”’')\]»」』》]*(?=\s|$)|[。！？]+["”’')\]»」』》]*"""
)
_CLOSING_QUOTES_AND_BRACKETS = "\"”’')]»」』》"
_ABBREVIATIONS = frozenset(
    {
        "mr.",
        "mrs.",
        "ms.",
        "dr.",
        "prof.",
        "sr.",
        "jr.",
        "st.",
        "e.g.",
        "i.e.",
        "u.s.",
        "u.k.",
        "vs.",
        "etc.",
        "jan.",
        "feb.",
        "mar.",
        "apr.",
        "jun.",
        "jul.",
        "aug.",
        "sep.",
        "sept.",
        "oct.",
        "nov.",
        "dec.",
    }
)


@dataclass(frozen=True)
class TextProcessingSettings:
    """Bounded text/audio controls; zero sentence pause preserves engine prosody."""

    max_chunk_characters: int = 1000
    sentence_pause_seconds: float = 0.0
    paragraph_pause_seconds: float = 0.35

    def __post_init__(self) -> None:
        if self.max_chunk_characters < 20:
            raise ValueError("Chunk size must be at least 20 characters.")
        for duration in (self.sentence_pause_seconds, self.paragraph_pause_seconds):
            if not math.isfinite(duration) or not 0 <= duration <= 5:
                raise ValueError(
                    "Pause duration must be between zero and five seconds."
                )


@dataclass(frozen=True)
class SpeechChunk:
    """One exact normalized source span, with no semantic rewriting of its text."""

    index: int
    dialogue_index: int
    speaker: str
    voice_id: str
    text: str
    source_start: int
    source_end: int
    pause_before_seconds: float


def normalize_text(text: str) -> str:
    """Normalize canonical Unicode/spacing without expanding dates or abbreviations."""
    normalized = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", " ", normalized).strip()


def _sentence_boundaries(text: str) -> list[int]:
    boundaries = []
    for match in _SENTENCE_END.finditer(text):
        suffix = text[max(0, match.start() - 16) : match.end()]
        suffix = suffix.rstrip(_CLOSING_QUOTES_AND_BRACKETS)
        word = suffix.split()[-1].lstrip("\"“‘'(")
        if word.casefold() in _ABBREVIATIONS:
            continue
        if len(word) == 2 and word[0].isalpha() and word[1] == ".":
            continue
        end = match.end()
        while end < len(text) and text[end].isspace():
            end += 1
        boundaries.append(end)
    return boundaries


def _safe_hard_boundary(text: str, start: int, end: int) -> int:
    """Avoid separating combining marks, variation selectors, and joined emoji."""
    while end > start and end < len(text):
        character = text[end]
        attached = (
            unicodedata.category(character).startswith("M")
            or character == "\u200d"
            or text[end - 1] == "\u200d"
            or "\U0001f3fb" <= character <= "\U0001f3ff"
        )
        if not attached:
            return end
        end -= 1
    if end == start:
        raise ValueError("A Unicode cluster exceeds the configured chunk limit.")
    return end


def split_text(
    text: str, max_characters: int, split_sentences: bool = False
) -> tuple[tuple[int, int], ...]:
    """Partition all source characters, preferring sentences and then whitespace."""
    if max_characters < 1:
        raise ValueError("Chunk length must be positive.")
    boundaries = _sentence_boundaries(text)
    spans = []
    start = 0
    while start < len(text):
        limit = min(start + max_characters, len(text))
        first = bisect_right(boundaries, start)
        last = bisect_right(boundaries, limit)
        candidates = boundaries[first:last]
        if split_sentences and candidates:
            end = candidates[0]
        elif limit == len(text):
            end = limit
        elif candidates:
            end = candidates[-1]
        else:
            spaces = list(re.finditer(r"\s+", text[start:limit]))
            if spaces:
                end = start + spaces[-1].end()
            else:
                end = _safe_hard_boundary(text, start, limit)
        spans.append((start, end))
        start = end
    return tuple(spans)


def chunk_conversation(
    lines: list[ConversationLine],
    settings: TextProcessingSettings,
    provider_limit: int | None,
) -> tuple[SpeechChunk, ...]:
    """Preserve dialogue and normalized character order within provider limits."""
    limit = settings.max_chunk_characters
    if provider_limit is not None:
        limit = min(limit, provider_limit)
    chunks = []
    for line in lines:
        text = normalize_text(line.text)
        sentence_ends = set(_sentence_boundaries(text))
        spans = split_text(text, limit, settings.sentence_pause_seconds > 0)
        for offset, (start, end) in enumerate(spans):
            pause = 0.0
            if offset == 0 and line.paragraph_break_before:
                pause = settings.paragraph_pause_seconds
            elif offset > 0 and start in sentence_ends:
                pause = settings.sentence_pause_seconds
            chunks.append(
                SpeechChunk(
                    index=len(chunks) + 1,
                    dialogue_index=line.index,
                    speaker=line.speaker,
                    voice_id=line.voice,
                    text=text[start:end],
                    source_start=start,
                    source_end=end,
                    pause_before_seconds=pause,
                )
            )
    return tuple(chunks)
