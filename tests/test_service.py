import asyncio
from pathlib import Path

import pytest

from ttsapp.parser import ConversationLine
from ttsapp.service import generate_conversation


def test_generate_conversation_smoke(tmp_path: Path, monkeypatch):
    """End-to-end smoke test with the Edge TTS and FFmpeg adapters mocked out.

    This avoids requiring network access/credentials or a real ffmpeg binary
    while still exercising the full parse -> synthesize -> combine pipeline.
    Uses ``asyncio.run`` directly rather than an async test function so the
    suite does not require the pytest-asyncio plugin.
    """

    input_file = tmp_path / "conversation.txt"
    input_file.write_text(
        "Receptionist: Hello there.\nCaller: Hi, thanks for calling.\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "audio_parts"
    final_audio = tmp_path / "conversation.mp3"

    voices = {
        "Receptionist": "en-GB-SoniaNeural",
        "Caller": "en-GB-RyanNeural",
    }

    synthesized = []

    async def fake_synthesize_line(text, voice, output_file):
        synthesized.append((text, voice, output_file))
        output_file.write_bytes(b"fake-audio")
        return output_file

    combined = {}

    def fake_combine_audio(audio_files, output_dir, final_audio_path):
        combined["audio_files"] = audio_files
        final_audio_path.write_bytes(b"fake-final-audio")
        return final_audio_path

    monkeypatch.setattr(
        "ttsapp.service.tts_engine.synthesize_line", fake_synthesize_line
    )
    monkeypatch.setattr(
        "ttsapp.service.audio_combiner.combine_audio", fake_combine_audio
    )

    progress_calls = []

    def on_progress(index, total, line: ConversationLine):
        progress_calls.append((index, total, line.speaker))

    result = asyncio.run(
        generate_conversation(
            input_file=input_file,
            output_dir=output_dir,
            final_audio=final_audio,
            voices=voices,
            on_progress=on_progress,
        )
    )

    assert result == final_audio
    assert output_dir.exists()
    assert len(synthesized) == 2
    assert synthesized[0][1] == "en-GB-SoniaNeural"
    assert synthesized[1][1] == "en-GB-RyanNeural"
    assert len(combined["audio_files"]) == 2
    assert progress_calls == [(1, 2, "Receptionist"), (2, 2, "Caller")]


def test_generate_conversation_accepts_in_memory_text(tmp_path: Path, monkeypatch):
    """The desktop UI (M02) passes ``input_text`` directly instead of a file."""

    output_dir = tmp_path / "audio_parts"
    final_audio = tmp_path / "conversation.mp3"

    voices = {
        "Receptionist": "en-GB-SoniaNeural",
        "Caller": "en-GB-RyanNeural",
    }

    synthesized = []

    async def fake_synthesize_line(text, voice, output_file):
        synthesized.append((text, voice, output_file))
        output_file.write_bytes(b"fake-audio")
        return output_file

    def fake_combine_audio(audio_files, output_dir, final_audio_path):
        final_audio_path.write_bytes(b"fake-final-audio")
        return final_audio_path

    monkeypatch.setattr(
        "ttsapp.service.tts_engine.synthesize_line", fake_synthesize_line
    )
    monkeypatch.setattr(
        "ttsapp.service.audio_combiner.combine_audio", fake_combine_audio
    )

    result = asyncio.run(
        generate_conversation(
            output_dir=output_dir,
            final_audio=final_audio,
            voices=voices,
            input_text="Receptionist: Hello there.\nCaller: Hi, thanks for calling.\n",
        )
    )

    assert result == final_audio
    assert len(synthesized) == 2
    assert synthesized[0][0] == "Hello there."
    assert synthesized[1][0] == "Hi, thanks for calling."


def test_generate_conversation_rejects_empty_script_before_creating_outputs(
    tmp_path: Path,
):
    output_dir = tmp_path / "audio_parts"

    with pytest.raises(ValueError, match="at least one dialogue line"):
        asyncio.run(
            generate_conversation(
                output_dir=output_dir,
                final_audio=tmp_path / "conversation.mp3",
                input_text=" \n\n",
            )
        )

    assert not output_dir.exists()
