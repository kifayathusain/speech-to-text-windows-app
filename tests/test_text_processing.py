"""Text partitioning preserves content and treats punctuation conservatively."""

import unicodedata

import pytest

from ttsapp.parser import parse_conversation_text
from ttsapp.text_processing import (
    TextProcessingSettings,
    chunk_conversation,
    normalize_text,
    split_text,
)


@pytest.mark.parametrize(
    "text",
    [
        "Dr. Smith paid $3.14 on Jan. 5. The U.S. office opens at 9:30.",
        "A sentence without punctuation " * 100,
        "extraordinarilylongword" * 50,
        "こんにちは。今日は晴れです！次の文章です。" * 20,
        '"Hello!" she said. This is another sentence? Yes.',
        "Emoji 👩\u200d💻 and canonical Café. " * 10,
    ],
)
def test_chunk_spans_cover_every_character_once_within_limit(text: str) -> None:
    spans = split_text(text, 40)

    assert "".join(text[start:end] for start, end in spans) == text
    assert all(0 < end - start <= 40 for start, end in spans)
    assert spans[0][0] == 0
    assert spans[-1][1] == len(text)
    assert all(
        first[1] == second[0]
        for first, second in zip(spans[:-1], spans[1:], strict=True)
    )


def test_sentence_chunking_keeps_common_abbreviations_and_decimal_numbers() -> None:
    text = "Dr. Smith met A. Jones in the U.S. on Jan. 5 at 9:30. They paid $3.14."
    chunks = [text[start:end] for start, end in split_text(text, 100, True)]

    assert chunks == [
        "Dr. Smith met A. Jones in the U.S. on Jan. 5 at 9:30. ",
        "They paid $3.14.",
    ]


def test_normalization_preserves_meaning_punctuation_and_original_input() -> None:
    original = "  Cafe\u0301\t Dr. Smith  —  10/24/2026, $3.14!  "

    assert normalize_text(original) == "Café Dr. Smith — 10/24/2026, $3.14!"
    assert "\u0301" in original


def test_blank_script_lines_become_paragraph_metadata_without_changing_dialogue() -> (
    None
):
    lines = parse_conversation_text(
        "\nCaller: First.\n\n\nCaller: Second.\nCaller: Third.\n", {"Caller": "voice"}
    )

    assert [line.index for line in lines] == [1, 2, 3]
    assert [line.paragraph_break_before for line in lines] == [False, True, False]
    chunks = chunk_conversation(lines, TextProcessingSettings(), 100)
    assert [chunk.pause_before_seconds for chunk in chunks] == [0, 0.35, 0]


def test_explicit_sentence_pauses_apply_only_to_sentence_boundaries() -> None:
    lines = parse_conversation_text(
        "Caller: Dr. Smith arrived. Hello! Goodbye.", {"Caller": "v"}
    )
    settings = TextProcessingSettings(sentence_pause_seconds=0.15)
    chunks = chunk_conversation(lines, settings, 100)

    assert [chunk.text for chunk in chunks] == [
        "Dr. Smith arrived. ",
        "Hello! ",
        "Goodbye.",
    ]
    assert [chunk.pause_before_seconds for chunk in chunks] == [0, 0.15, 0.15]


def test_provider_limit_is_enforced_even_when_settings_allow_larger_chunks() -> None:
    lines = parse_conversation_text("Caller: " + "word " * 100, {"Caller": "v"})
    chunks = chunk_conversation(
        lines, TextProcessingSettings(max_chunk_characters=1000), 30
    )

    assert all(len(chunk.text) <= 30 for chunk in chunks)
    assert "".join(chunk.text for chunk in chunks) == normalize_text(lines[0].text)


def test_hard_boundary_does_not_separate_combining_mark_from_its_base() -> None:
    text = "x" * 19 + "a\u0301" + "y" * 20
    spans = split_text(text, 20)

    assert all(not unicodedata.combining(text[start]) for start, end in spans)
    assert "".join(text[start:end] for start, end in spans) == text


@pytest.mark.parametrize("duration", [-1, 6, float("nan"), float("inf")])
def test_pause_configuration_rejects_invalid_or_excessive_silence(
    duration: float,
) -> None:
    with pytest.raises(ValueError, match="Pause duration"):
        TextProcessingSettings(paragraph_pause_seconds=duration)
