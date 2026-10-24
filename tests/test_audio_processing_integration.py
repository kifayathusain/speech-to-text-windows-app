"""Real FFmpeg conversion of controlled Edge MP3 segments into processed output."""

import asyncio
import os
import subprocess
import wave
from pathlib import Path

import pytest

from ttsapp import tts_engine
from ttsapp.service import generate_conversation
from ttsapp.text_processing import TextProcessingSettings


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("TTS_FFMPEG_TESTS") != "1",
    reason="Set TTS_FFMPEG_TESTS=1 with a real FFmpeg executable on PATH.",
)
def test_processed_edge_decodes_mp3_to_lossless_intermediates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "tone.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.2",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    native_bytes = source.read_bytes()

    class ControlledCommunicate:
        def __init__(self, text: str, voice: str) -> None:
            pass

        async def save(self, path: str) -> None:
            Path(path).write_bytes(native_bytes)

    monkeypatch.setattr(tts_engine.edge_tts, "Communicate", ControlledCommunicate)
    output = tmp_path / "final.wav"
    parts = tmp_path / "parts"
    asyncio.run(
        generate_conversation(
            input_text="Caller: First.\n\nCaller: Second.",
            output_dir=parts,
            final_audio=output,
            text_settings=TextProcessingSettings(),
        )
    )

    expected_frames = 0
    for file in parts.rglob("*.wav"):
        with wave.open(str(file)) as audio:
            expected_frames += audio.getnframes()
    with wave.open(str(output)) as audio:
        assert audio.getframerate() == 44100
        assert audio.getsampwidth() == 2
        assert audio.getnframes() == expected_frames
