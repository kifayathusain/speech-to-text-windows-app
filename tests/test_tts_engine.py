import asyncio
from pathlib import Path

import pytest

from ttsapp import tts_engine


def test_synthesize_line_saves_unicode_audio_atomically(tmp_path: Path, monkeypatch):
    output_file = tmp_path / "nested" / "line_001.mp3"
    calls = {}

    class FakeCommunicate:
        def __init__(self, text, voice):
            calls["text"] = text
            calls["voice"] = voice

        async def save(self, path):
            calls["temporary_path"] = Path(path)
            Path(path).write_bytes(b"complete-audio")

    monkeypatch.setattr(tts_engine.edge_tts, "Communicate", FakeCommunicate)

    result = asyncio.run(
        tts_engine.synthesize_line(
            "Bonjour, café! こんにちは。", "en-GB-SoniaNeural", output_file
        )
    )

    assert result == output_file
    assert calls["text"] == "Bonjour, café! こんにちは。"
    assert calls["voice"] == "en-GB-SoniaNeural"
    assert calls["temporary_path"] != output_file
    assert output_file.read_bytes() == b"complete-audio"
    assert list(output_file.parent.iterdir()) == [output_file]


def test_synthesize_line_handles_long_unicode_text_and_overwrites_output(
    tmp_path: Path, monkeypatch
):
    output_file = tmp_path / "line_001.mp3"
    output_file.write_bytes(b"previous-audio")
    text = ("Café こんにちは — " * 2_000).strip()
    captured = {}

    class LongTextCommunicate:
        def __init__(self, text, voice):
            captured["text"] = text

        async def save(self, path):
            Path(path).write_bytes(b"new-audio")

    monkeypatch.setattr(tts_engine.edge_tts, "Communicate", LongTextCommunicate)

    asyncio.run(tts_engine.synthesize_line(text, "en-GB-SoniaNeural", output_file))

    assert captured["text"] == text
    assert output_file.read_bytes() == b"new-audio"
    assert list(tmp_path.iterdir()) == [output_file]


def test_synthesize_line_removes_partial_temp_and_preserves_existing_output(
    tmp_path: Path, monkeypatch
):
    output_file = tmp_path / "line_001.mp3"
    output_file.write_bytes(b"previous-valid-audio")

    class FailingCommunicate:
        def __init__(self, text, voice):
            pass

        async def save(self, path):
            Path(path).write_bytes(b"partial-audio")
            raise RuntimeError("connection closed")

    monkeypatch.setattr(tts_engine.edge_tts, "Communicate", FailingCommunicate)

    with pytest.raises(tts_engine.TTSGenerationError, match="connection closed"):
        asyncio.run(
            tts_engine.synthesize_line("Hello", "en-GB-SoniaNeural", output_file)
        )

    assert output_file.read_bytes() == b"previous-valid-audio"
    assert list(tmp_path.iterdir()) == [output_file]


def test_synthesize_line_cancellation_cleans_temporary_file_and_preserves_output(
    tmp_path: Path, monkeypatch
):
    output_file = tmp_path / "line_001.mp3"
    output_file.write_bytes(b"previous-valid-audio")

    class CancelledCommunicate:
        def __init__(self, text, voice):
            pass

        async def save(self, path):
            Path(path).write_bytes(b"partial-audio")
            raise asyncio.CancelledError

    monkeypatch.setattr(tts_engine.edge_tts, "Communicate", CancelledCommunicate)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            tts_engine.synthesize_line("Hello", "en-GB-SoniaNeural", output_file)
        )

    assert output_file.read_bytes() == b"previous-valid-audio"
    assert list(tmp_path.iterdir()) == [output_file]


@pytest.mark.parametrize(
    ("text", "voice", "message"),
    [
        ("", "en-GB-SoniaNeural", "Speech text cannot be empty"),
        ("  \n", "en-GB-SoniaNeural", "Speech text cannot be empty"),
        ("Hello", "", "voice must be selected"),
        ("Hello", "  ", "voice must be selected"),
    ],
)
def test_synthesize_line_rejects_empty_input_before_creating_output(
    tmp_path: Path, text: str, voice: str, message: str, monkeypatch
):
    def unexpected_communicate(**kwargs):
        pytest.fail("Edge TTS should not be called for invalid input")

    monkeypatch.setattr(tts_engine.edge_tts, "Communicate", unexpected_communicate)

    with pytest.raises(ValueError, match=message):
        asyncio.run(
            tts_engine.synthesize_line(text, voice, tmp_path / "line.mp3")
        )

    assert list(tmp_path.iterdir()) == []


def test_synthesize_line_rejects_empty_edge_tts_output(tmp_path: Path, monkeypatch):
    class EmptyCommunicate:
        def __init__(self, text, voice):
            pass

        async def save(self, path):
            Path(path).touch()

    monkeypatch.setattr(tts_engine.edge_tts, "Communicate", EmptyCommunicate)
    output_file = tmp_path / "line.mp3"

    with pytest.raises(tts_engine.TTSGenerationError, match="empty audio file"):
        asyncio.run(
            tts_engine.synthesize_line("Hello", "en-GB-SoniaNeural", output_file)
        )

    assert not output_file.exists()
    assert list(tmp_path.iterdir()) == []
