"""Opt-in real Kokoro-82M CPU synthesis, voices, and export validation."""

import asyncio
import os
import socket
import subprocess
import wave
from array import array
from pathlib import Path

import pytest

from ttsapp.models.kokoro_catalog import kokoro_v1_model
from ttsapp.providers.base import SynthesisRequest
from ttsapp.providers.kokoro import KokoroTTSProvider
from ttsapp.service import generate_conversation


@pytest.mark.integration
@pytest.mark.real_model
@pytest.mark.skipif(
    not os.environ.get("TTS_KOKORO_MODEL_DIR"),
    reason="Set TTS_KOKORO_MODEL_DIR with Python 3.10–3.13 and real assets/FFmpeg.",
)
def test_real_kokoro_offline_cpu_multiple_voices_and_mp3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kokoro_onnx import Kokoro

    sessions: list[list[str]] = []
    original_from_session = Kokoro.from_session

    def from_session(session: object, *args: object, **kwargs: object) -> Kokoro:
        sessions.append(session.get_providers())
        return original_from_session(session, *args, **kwargs)

    def no_network(*args: object, **kwargs: object) -> object:
        pytest.fail("Offline Kokoro must not use DNS or network connection helpers")

    monkeypatch.setattr(Kokoro, "from_session", from_session)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    model = kokoro_v1_model(Path(os.environ["TTS_KOKORO_MODEL_DIR"]))
    provider = KokoroTTSProvider(model)
    output = tmp_path / "native.wav"
    final_audio = tmp_path / "conversation.mp3"
    decoded = tmp_path / "decoded.wav"
    try:
        asyncio.run(
            provider.synthesize(
                SynthesisRequest(
                    "Hello from the local Kokoro voice.", "af_heart", "wav"
                ),
                output,
            )
        )
        with wave.open(str(output)) as audio:
            assert audio.getframerate() == 24000
            assert audio.getnframes() > 12000
            samples = array("h", audio.readframes(audio.getnframes()))
            assert max(abs(sample) for sample in samples) > 100

        asyncio.run(
            generate_conversation(
                input_text="First: Hello from Heart.\nSecond: This is a British voice.",
                voices={"First": "af_heart", "Second": "bf_emma"},
                output_dir=tmp_path / "parts",
                final_audio=final_audio,
                provider_id="kokoro",
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
        with wave.open(str(decoded)) as audio:
            assert audio.getframerate() == 24000
            assert audio.getnframes() > 24000
    finally:
        provider.close()
