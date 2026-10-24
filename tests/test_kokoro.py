"""Kokoro metadata and validation remain usable without optional inference deps."""

import asyncio
import hashlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from ttsapp.models.assets import ModelAsset, ModelValidationError
from ttsapp.providers.base import CancellationToken, SynthesisRequest, VoiceMetadata
from ttsapp.providers.kokoro import KokoroModel, KokoroSynthesisError, KokoroTTSProvider


@pytest.fixture
def kokoro_model(tmp_path: Path) -> KokoroModel:
    assets = []
    for name in ("model.onnx", "voices.bin"):
        path = tmp_path / name
        data = name.encode()
        path.write_bytes(data)
        assets.append(ModelAsset(path, hashlib.sha256(data).hexdigest()))
    return KokoroModel(
        assets[0], assets[1], (VoiceMetadata("af_heart", "Heart", "en-US"),)
    )


def test_kokoro_metadata_does_not_load_optional_runtime(
    kokoro_model: KokoroModel,
) -> None:
    provider = KokoroTTSProvider(kokoro_model)

    assert provider.get_available_voices() == kokoro_model.voices
    assert provider.get_capabilities().audio_formats == ("wav",)
    assert not provider.get_capabilities().online
    assert provider.get_capabilities().max_text_characters == 2000
    provider.close()


@pytest.mark.parametrize(
    ("synthesis_request", "message"),
    [
        (SynthesisRequest(" ", "af_heart", "wav"), "text cannot be empty"),
        (SynthesisRequest("a" * 2001, "af_heart", "wav"), "2000 characters"),
        (SynthesisRequest("Hello", "missing", "wav"), "Unknown Kokoro voice"),
        (SynthesisRequest("Hello", "af_heart", "mp3"), "native WAV"),
        (SynthesisRequest("Hello", "af_heart", "wav", speed=0.1), "between"),
        (SynthesisRequest("Hello", "af_heart", "wav", speed=float("nan")), "between"),
        (SynthesisRequest("Hello", "af_heart", "wav", language="fr-FR"), "language"),
    ],
)
def test_kokoro_validates_settings_before_inference(
    kokoro_model: KokoroModel,
    synthesis_request: SynthesisRequest,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        KokoroTTSProvider(kokoro_model).validate_configuration(synthesis_request)


def test_kokoro_checks_model_integrity(kokoro_model: KokoroModel) -> None:
    kokoro_model.voice_data.path.write_bytes(b"changed")

    with pytest.raises(ModelValidationError, match="checksum mismatch"):
        KokoroTTSProvider(kokoro_model).validate_configuration(
            SynthesisRequest("Hello", "af_heart", "wav")
        )


def test_kokoro_cancellation_prevents_loading_and_writes(
    kokoro_model: KokoroModel, tmp_path: Path
) -> None:
    output = tmp_path / "output.wav"
    token = CancellationToken()
    token.cancel()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            KokoroTTSProvider(kokoro_model).synthesize(
                SynthesisRequest("Hello", "af_heart", "wav"), output, token
            )
        )

    assert not output.exists()


def test_kokoro_runtime_failure_preserves_existing_output(
    kokoro_model: KokoroModel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = KokoroTTSProvider(kokoro_model)
    output = tmp_path / "output.wav"
    output.write_bytes(b"previous")

    def unavailable() -> None:
        raise KokoroSynthesisError("Runtime unavailable")

    monkeypatch.setattr(provider, "_load_engine", unavailable)
    with pytest.raises(KokoroSynthesisError, match="Runtime unavailable"):
        asyncio.run(
            provider.synthesize(SynthesisRequest("Hello", "af_heart", "wav"), output)
        )

    assert output.read_bytes() == b"previous"
    assert not list(tmp_path.glob(".output.*"))


def test_kokoro_keeps_verified_styles_resident_and_rechecks_on_reload(
    kokoro_model: KokoroModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Warm use needs no archive reads; closing never bypasses hash verification."""
    closed = []
    copied = []

    class Style:
        def copy(self) -> "Style":
            copied.append(True)
            return self

        def setflags(self, *, write: bool) -> None:
            assert write is False

    engine = SimpleNamespace(
        voices=SimpleNamespace(close=lambda: closed.append(True)),
        get_voices=lambda: ["af_heart"],
        get_voice_style=lambda identifier: Style(),
    )
    runtime = ModuleType("kokoro_onnx")
    runtime.Kokoro = SimpleNamespace(from_session=lambda *args: engine)
    monkeypatch.setitem(sys.modules, "kokoro_onnx", runtime)
    monkeypatch.setattr("ttsapp.providers.kokoro.sys.version_info", (3, 13))
    monkeypatch.setattr(
        "ttsapp.providers.kokoro.create_cpu_session", lambda *args: object()
    )
    provider = KokoroTTSProvider(kokoro_model)
    provider.prepare()
    assert closed == [True]
    assert copied == [True]

    kokoro_model.voice_data.path.write_bytes(b"changed on disk")
    provider.validate_configuration(SynthesisRequest("Hello", "af_heart", "wav"))
    provider.prepare()
    assert copied == [True]
    provider.close()
    with pytest.raises(ModelValidationError, match="checksum mismatch"):
        provider.prepare()


def test_kokoro_load_rechecks_after_successful_prevalidation(
    kokoro_model: KokoroModel,
) -> None:
    provider = KokoroTTSProvider(kokoro_model)
    provider.validate_configuration(SynthesisRequest("Hello", "af_heart", "wav"))
    kokoro_model.model.path.write_bytes(b"changed after validation")
    with pytest.raises(ModelValidationError, match="checksum mismatch"):
        provider.prepare()
