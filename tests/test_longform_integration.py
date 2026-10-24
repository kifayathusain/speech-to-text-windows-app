"""Opt-in real long-form CPU generation and lossless chunk-order validation."""

import asyncio
import json
import os
import socket
import subprocess
import wave
from pathlib import Path

import pytest

from ttsapp.models.piper_catalog import lessac_low_model
from ttsapp.providers.piper import PiperTTSProvider
from ttsapp.service import generate_conversation
from ttsapp.text_processing import SpeechChunk, TextProcessingSettings


@pytest.mark.integration
@pytest.mark.real_model
@pytest.mark.skipif(
    not os.environ.get("TTS_LONGFORM_MODEL_DIR"),
    reason="Set TTS_LONGFORM_MODEL_DIR to verified Piper assets and provide FFmpeg.",
)
def test_real_long_text_preserves_source_and_export_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_network(*args: object, **kwargs: object) -> object:
        pytest.fail("Long-form local inference must not use network helpers")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    model = lessac_low_model(Path(os.environ["TTS_LONGFORM_MODEL_DIR"]))
    provider = PiperTTSProvider((model,))
    sentences = [
        f"Section {index} describes the journey. Dr. Smith recorded the time as "
        "9:30, checked the $3.14 total, and preserved every note for the next day."
        for index in range(1, 17)
    ]
    paragraphs = [" ".join(sentences[:8]), " ".join(sentences[8:])]
    source = f"Narrator: {paragraphs[0]}\n\nNarrator: {paragraphs[1]}"
    assert sum(map(len, paragraphs)) > 2000
    chunks: list[SpeechChunk] = []
    final = tmp_path / "long.mp3"
    decoded = tmp_path / "decoded.wav"
    parts = tmp_path / "parts"
    try:
        asyncio.run(
            generate_conversation(
                input_text=source,
                voices={"Narrator": model.voice.voice_id},
                provider_id="piper",
                provider=provider,
                output_dir=parts,
                final_audio=final,
                text_settings=TextProcessingSettings(max_chunk_characters=240),
                on_chunk_progress=lambda index, total, chunk: chunks.append(chunk),
            )
        )
        for index, paragraph in enumerate(paragraphs, start=1):
            assert (
                "".join(chunk.text for chunk in chunks if chunk.dialogue_index == index)
                == paragraph
            )
        assert len({chunk.index for chunk in chunks}) == len(chunks)
        assert all(len(chunk.text) <= 240 for chunk in chunks)
        metadata = json.loads(next(parts.glob("job-*/generation.json")).read_text())
        assert metadata["state"] == "done"
        assert len(metadata["chunks"]) == len(chunks)
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(final),
                "-c:a",
                "pcm_s16le",
                str(decoded),
            ],
            check=True,
            capture_output=True,
        )
        source_frames = 0
        for file in parts.rglob("*.wav"):
            with wave.open(str(file)) as audio:
                source_frames += audio.getnframes()
        with wave.open(str(decoded)) as audio:
            assert abs(audio.getnframes() - source_frames) < audio.getframerate() // 4
    finally:
        provider.close()
