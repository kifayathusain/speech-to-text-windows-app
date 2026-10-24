"""Opt-in fresh downloads, local inference, and removal of real catalog models."""

import asyncio
import os
import socket
import wave
from pathlib import Path

import pytest

from ttsapp.models.kokoro_catalog import kokoro_v1_model
from ttsapp.models.manager import InstallationState, ModelManager
from ttsapp.models.piper_catalog import lessac_low_model
from ttsapp.providers.base import SynthesisRequest
from ttsapp.providers.kokoro import KokoroTTSProvider
from ttsapp.providers.piper import PiperTTSProvider


@pytest.mark.integration
@pytest.mark.real_model
@pytest.mark.skipif(
    os.environ.get("TTS_MODEL_DOWNLOAD_TESTS") != "1",
    reason="Set TTS_MODEL_DOWNLOAD_TESTS=1 to explicitly download real catalog models.",
)
@pytest.mark.parametrize("model_id", ["kokoro-82m-v1", "piper-lessac-low"])
def test_fresh_model_download_verify_use_and_remove(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_id: str,
) -> None:
    manager = ModelManager(tmp_path / "models")
    assert manager.status(model_id) == InstallationState.NOT_INSTALLED
    directory = manager.install(model_id)
    assert manager.status(model_id) == InstallationState.INSTALLED

    def no_network(*args: object, **kwargs: object) -> object:
        pytest.fail("Installed model synthesis must remain offline")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    if model_id == "kokoro-82m-v1":
        provider = KokoroTTSProvider(kokoro_v1_model(directory))
        voice_id = "af_heart"
    else:
        model = lessac_low_model(directory)
        provider = PiperTTSProvider((model,))
        voice_id = model.voice.voice_id
    output = tmp_path / "fresh-model.wav"
    try:
        asyncio.run(
            provider.synthesize(
                SynthesisRequest("A fresh model runs locally.", voice_id, "wav"), output
            )
        )
        with wave.open(str(output)) as audio:
            assert audio.getnframes() > audio.getframerate() // 2
    finally:
        provider.close()

    manager.remove(model_id)
    assert manager.status(model_id) == InstallationState.NOT_INSTALLED
    assert not directory.exists()
