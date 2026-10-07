from pathlib import Path

import pytest

from ttsapp.parser import UnknownSpeakerError, parse_conversation, parse_conversation_text

VOICES = {
    "Receptionist": "en-GB-SoniaNeural",
    "Caller": "en-GB-RyanNeural",
}


def test_parse_conversation_parses_lines_in_order(tmp_path: Path):
    script = tmp_path / "conversation.txt"
    script.write_text(
        "Receptionist: Hello there.\n"
        "\n"
        "Caller: Hi, I have a question.\n",
        encoding="utf-8",
    )

    lines = parse_conversation(script, VOICES)

    assert len(lines) == 2

    assert lines[0].index == 1
    assert lines[0].speaker == "Receptionist"
    assert lines[0].text == "Hello there."
    assert lines[0].voice == "en-GB-SoniaNeural"

    assert lines[1].index == 2
    assert lines[1].speaker == "Caller"
    assert lines[1].text == "Hi, I have a question."
    assert lines[1].voice == "en-GB-RyanNeural"


def test_parse_conversation_skips_blank_lines(tmp_path: Path):
    script = tmp_path / "conversation.txt"
    script.write_text("\n\nReceptionist: Hello.\n\n\n", encoding="utf-8")

    lines = parse_conversation(script, VOICES)

    assert len(lines) == 1
    assert lines[0].text == "Hello."


def test_parse_conversation_raises_on_unknown_speaker(tmp_path: Path):
    script = tmp_path / "conversation.txt"
    script.write_text("Narrator: This speaker is not configured.\n", encoding="utf-8")

    with pytest.raises(UnknownSpeakerError):
        parse_conversation(script, VOICES)


def test_parse_conversation_raises_on_malformed_line(tmp_path: Path):
    script = tmp_path / "conversation.txt"
    script.write_text("This line has no colon separator\n", encoding="utf-8")

    with pytest.raises(ValueError):
        parse_conversation(script, VOICES)


def test_parse_conversation_handles_colons_in_dialogue(tmp_path: Path):
    script = tmp_path / "conversation.txt"
    script.write_text("Receptionist: The time is 6:30 PM.\n", encoding="utf-8")

    lines = parse_conversation(script, VOICES)

    assert lines[0].text == "The time is 6:30 PM."


def test_parse_conversation_text_matches_file_based_parsing(tmp_path: Path):
    """The desktop UI feeds text directly; it must parse identically to a file."""

    script_text = "Receptionist: Hello there.\n\nCaller: Hi, I have a question.\n"

    script = tmp_path / "conversation.txt"
    script.write_text(script_text, encoding="utf-8")

    from_file = parse_conversation(script, VOICES)
    from_text = parse_conversation_text(script_text, VOICES)

    assert from_file == from_text


def test_parse_conversation_text_raises_on_unknown_speaker():
    with pytest.raises(UnknownSpeakerError):
        parse_conversation_text("Narrator: Not configured.\n", VOICES)


def test_parse_conversation_text_raises_on_malformed_line():
    with pytest.raises(ValueError):
        parse_conversation_text("No colon here\n", VOICES)
