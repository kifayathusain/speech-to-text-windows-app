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


def test_generate_conversation_stops_after_tts_failure(tmp_path: Path, monkeypatch):
    output_dir = tmp_path / "audio_parts"
    final_audio = tmp_path / "conversation.mp3"
    final_audio.write_bytes(b"previous-valid-audio")
    synthesized = []
    combined = []

    async def fake_synthesize_line(text, voice, output_file):
        synthesized.append(text)
        if text == "Second line":
            raise RuntimeError("TTS service unavailable")
        output_file.write_bytes(b"first-line-audio")

    def unexpected_combine(*args):
        combined.append(args)
        pytest.fail("Audio must not be combined after a synthesis failure")

    monkeypatch.setattr(
        "ttsapp.service.tts_engine.synthesize_line", fake_synthesize_line
    )
    monkeypatch.setattr(
        "ttsapp.service.audio_combiner.combine_audio", unexpected_combine
    )
    progress = []

    with pytest.raises(RuntimeError, match="TTS service unavailable"):
        asyncio.run(
            generate_conversation(
                output_dir=output_dir,
                final_audio=final_audio,
                voices={"Caller": "en-GB-RyanNeural"},
                input_text="Caller: First line\nCaller: Second line",
                on_progress=lambda index, total, line: progress.append(index),
            )
        )

    assert synthesized == ["First line", "Second line"]
    assert combined == []
    assert progress == [1]
    assert final_audio.read_bytes() == b"previous-valid-audio"


def test_generate_conversation_repeated_runs_overwrite_final_and_use_current_lines(
    tmp_path: Path, monkeypatch
):
    output_dir = tmp_path / "audio_parts"
    final_audio = tmp_path / "exports" / "conversation.mp3"
    combined_inputs = []

    async def fake_synthesize_line(text, voice, output_file):
        output_file.write_text(text, encoding="utf-8")

    def fake_combine_audio(audio_files, output_dir, final_audio_path):
        combined_inputs.append([path.name for path in audio_files])
        final_audio_path.parent.mkdir(parents=True, exist_ok=True)
        final_audio_path.write_text(
            "|".join(path.read_text(encoding="utf-8") for path in audio_files),
            encoding="utf-8",
        )
        return final_audio_path

    monkeypatch.setattr(
        "ttsapp.service.tts_engine.synthesize_line", fake_synthesize_line
    )
    monkeypatch.setattr(
        "ttsapp.service.audio_combiner.combine_audio", fake_combine_audio
    )

    async def generate(script):
        return await generate_conversation(
            output_dir=output_dir,
            final_audio=final_audio,
            voices={"Caller": "en-GB-RyanNeural"},
            input_text=script,
        )

    asyncio.run(generate("Caller: First run\nCaller: First run, second line"))
    asyncio.run(generate("Caller: Second run"))

    assert final_audio.read_text(encoding="utf-8") == "Second run"
    assert combined_inputs == [
        ["line_001.mp3", "line_002.mp3"],
        ["line_001.mp3"],
    ]
