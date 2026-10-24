"""Opt-in real CPU inference and media conversion; never downloads test assets."""

import asyncio
import os
import socket
import subprocess
import wave
from array import array
from pathlib import Path

import pytest

from ttsapp.models.piper_catalog import lessac_low_model
from ttsapp.providers.base import SynthesisRequest
from ttsapp.providers.piper import PiperTTSProvider
from ttsapp.service import generate_conversation


@pytest.mark.integration
@pytest.mark.real_model
@pytest.mark.skipif(
    not os.environ.get("TTS_PIPER_MODEL_DIR"),
    reason="Set TTS_PIPER_MODEL_DIR to opt into installed real voice/FFmpeg tests.",
)
def test_real_piper_offline_wav_and_conversation_mp3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove local CPU speech, session reuse, and correctly encoded final media."""
    import onnxruntime

    model = lessac_low_model(Path(os.environ["TTS_PIPER_MODEL_DIR"]))
    provider = PiperTTSProvider((model,))
    original_load = onnxruntime.InferenceSession
    sessions: list[list[str]] = []

    def load(*args: object, **kwargs: object) -> object:
        session = original_load(*args, **kwargs)
        sessions.append(session.get_providers())
        assert kwargs["sess_options"].intra_op_num_threads == 4
        return session

    def no_network(*args: object, **kwargs: object) -> object:
        pytest.fail("Offline inference must not use DNS or network connections")

    monkeypatch.setattr(onnxruntime, "InferenceSession", load)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    output = tmp_path / "native.wav"
    final_audio = tmp_path / "conversation.mp3"
    decoded = tmp_path / "decoded.wav"
    parts = tmp_path / "parts"

    try:
        asyncio.run(
            provider.synthesize(
                SynthesisRequest(
                    "Hello from the offline CPU voice.", model.voice.voice_id, "wav"
                ),
                output,
            )
        )
        with wave.open(str(output)) as audio:
            assert audio.getframerate() == 16000
            assert audio.getsampwidth() == 2
            assert audio.getnchannels() == 1
            assert audio.getnframes() > audio.getframerate() // 2
            samples = array("h", audio.readframes(audio.getnframes()))
            assert max(abs(sample) for sample in samples) > 100

        asyncio.run(
            generate_conversation(
                input_text="Narrator: First offline sentence.\nNarrator: Second sentence.",
                voices={"Narrator": model.voice.voice_id},
                output_dir=parts,
                final_audio=final_audio,
                provider_id="piper",
                provider=provider,
            )
        )
        assert sessions == [["CPUExecutionProvider"]]
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(final_audio),
                "-c:a",
                "pcm_s16le",
                str(decoded),
            ],
            check=True,
            capture_output=True,
        )
        source_frames = 0
        for segment in parts.rglob("*.wav"):
            with wave.open(str(segment)) as audio:
                source_frames += audio.getnframes()
        with wave.open(str(decoded)) as audio:
            assert abs(audio.getnframes() - source_frames) < audio.getframerate() // 4
        assert not list(parts.glob(".concat-*"))
    finally:
        provider.close()
