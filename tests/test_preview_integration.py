"""Opt-in actual CPU previews with installed models and versioned cache reuse."""

import asyncio
import os
import socket
import wave
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse

import pytest

from ttsapp.models.manager import ModelManager
from ttsapp.preview import PreviewService
from ttsapp.provider_manager import ProviderManager


@pytest.mark.integration
@pytest.mark.real_model
@pytest.mark.skipif(
    not os.environ.get("TTS_PREVIEW_MODEL_ROOT"),
    reason="Set TTS_PREVIEW_MODEL_ROOT to verified kokoro/piper assets with Python 3.10–3.13.",
)
def test_real_provider_previews_cache_and_release_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assets = Path(os.environ["TTS_PREVIEW_MODEL_ROOT"])

    def open_cached_asset(url: str) -> BinaryIO:
        filename = Path(urlparse(url).path).name
        provider = (
            "piper"
            if filename.startswith("en_US-") or filename == "MODEL_CARD"
            else "kokoro"
        )
        return (assets / provider / filename).open("rb")

    def no_network(*args: object, **kwargs: object) -> object:
        pytest.fail("Real local previews must not use network helpers")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    models = ModelManager(tmp_path / "models", opener=open_cached_asset)
    models.install("kokoro-82m-v1")
    models.install("piper-lessac-low")
    providers = ProviderManager(models)
    previews = PreviewService(providers, tmp_path / "cache")
    try:
        for provider_id, voice in (
            ("kokoro", "af_heart"),
            ("piper", "en_US-lessac-low"),
        ):
            first = asyncio.run(
                previews.generate(
                    provider_id, voice, "This is the selected local voice.", 0.9
                )
            )
            repeated = asyncio.run(
                previews.generate(
                    provider_id, voice, "This is the selected local voice.", 0.9
                )
            )
            assert first == repeated
            with wave.open(str(first)) as audio:
                assert audio.getnframes() > audio.getframerate() // 2
                assert audio.getsampwidth() == 2
        models.remove("kokoro-82m-v1")
    finally:
        providers.close()
    models.remove("piper-lessac-low")
    assert not list((tmp_path / "cache").glob(".preview-*"))
