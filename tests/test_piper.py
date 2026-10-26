"""Offline-provider behavior using tiny local assets and a controlled runtime."""

import asyncio
import hashlib
import json
import sys
import threading
import wave
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from ttsapp.models.assets import ModelAsset, ModelValidationError
from ttsapp.providers.base import CancellationToken, SynthesisRequest, VoiceMetadata
from ttsapp.providers.piper import PiperModel, PiperSynthesisError, PiperTTSProvider


def make_asset(path: Path, contents: bytes) -> ModelAsset:
    """Write a tiny explicitly trusted test asset."""
    path.write_bytes(contents)
    return ModelAsset(path, hashlib.sha256(contents).hexdigest())


@pytest.fixture
def piper_model(tmp_path: Path) -> PiperModel:
    configuration = json.dumps(
        {"audio": {"sample_rate": 16000}, "phoneme_type": "espeak"}
    ).encode()
    return PiperModel(
        VoiceMetadata("test-voice", "Test", "en-US"),
        make_asset(tmp_path / "voice.onnx", b"controlled model"),
        make_asset(tmp_path / "voice.onnx.json", configuration),
    )


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(
        loads=0, length_scale=None, fail=False, empty=False, token=None
    )

    class Voice:
        config = SimpleNamespace(sample_rate=16000)

        def __init__(self, **kwargs: object) -> None:
            assert kwargs["use_tashkeel"] is False
            state.loads += 1

        def synthesize(
            self, text: str, settings: SimpleNamespace
        ) -> Iterator[SimpleNamespace]:
            state.length_scale = settings.length_scale
            state.speaker_id = settings.speaker_id
            if state.empty:
                return
            yield SimpleNamespace(audio_int16_bytes=b"\x01\x00" * 100)
            if state.token is not None:
                state.token.cancel()
            if state.fail:
                raise RuntimeError("inference failed")
            yield SimpleNamespace(audio_int16_bytes=b"\x02\x00" * 100)

    module = ModuleType("piper")
    module.PiperVoice = Voice
    module.PiperConfig = SimpleNamespace(from_dict=lambda value: value)
    monkeypatch.setattr(
        "ttsapp.providers.piper.create_cpu_session", lambda *args: object()
    )
    module.SynthesisConfig = lambda **kwargs: SimpleNamespace(**kwargs)
    monkeypatch.setitem(sys.modules, "piper", module)
    return state


def test_piper_discovery_is_lazy_and_reuses_cpu_session(
    piper_model: PiperModel,
    runtime: SimpleNamespace,
    tmp_path: Path,
) -> None:
    provider = PiperTTSProvider((piper_model,))
    assert provider.get_available_voices() == (piper_model.voice,)
    assert not provider.get_capabilities().online
    assert runtime.loads == 0

    for index in range(2):
        output = tmp_path / f"audio-{index}.wav"
        result = asyncio.run(
            provider.synthesize(
                SynthesisRequest("Café", "test-voice", "wav", speed=2), output
            )
        )
        assert result.output_file == output
        with wave.open(str(output)) as audio:
            assert audio.getnframes() == 200
            assert audio.getframerate() == 16000

    assert runtime.loads == 1
    assert runtime.length_scale == 0.5
    provider.close()
    asyncio.run(
        provider.synthesize(
            SynthesisRequest("Again", "test-voice", "wav"), tmp_path / "again.wav"
        )
    )
    assert runtime.loads == 2


@pytest.mark.parametrize("speed", [0, -1, float("nan"), float("inf")])
def test_piper_rejects_invalid_speed(piper_model: PiperModel, speed: float) -> None:
    provider = PiperTTSProvider((piper_model,))

    with pytest.raises(ValueError, match="finite positive"):
        provider.validate_configuration(
            SynthesisRequest("Hello", "test-voice", "wav", speed=speed)
        )


def test_piper_rejects_missing_and_corrupted_models(piper_model: PiperModel) -> None:
    provider = PiperTTSProvider((piper_model,))
    request = SynthesisRequest("Hello", "test-voice", "wav")
    piper_model.model.path.write_bytes(b"corrupted")
    with pytest.raises(ModelValidationError, match="checksum mismatch"):
        provider.validate_configuration(request)
    piper_model.model.path.unlink()
    with pytest.raises(ModelValidationError, match="missing"):
        provider.validate_configuration(request)


@pytest.mark.parametrize(
    ("synthesis_request", "message"),
    [
        (SynthesisRequest(" ", "test-voice", "wav"), "text cannot be empty"),
        (SynthesisRequest("Hello", "missing", "wav"), "Unknown Piper voice"),
        (SynthesisRequest("Hello", "test-voice", "mp3"), "native WAV"),
        (
            SynthesisRequest("Hello", "test-voice", "wav", language="fr-FR"),
            "language must match",
        ),
    ],
)
def test_piper_rejects_invalid_selection(
    piper_model: PiperModel,
    synthesis_request: SynthesisRequest,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        PiperTTSProvider((piper_model,)).validate_configuration(synthesis_request)


@pytest.mark.parametrize("mode", ["failure", "empty", "cancelled"])
def test_piper_cleans_incomplete_output_and_preserves_previous_export(
    piper_model: PiperModel,
    runtime: SimpleNamespace,
    tmp_path: Path,
    mode: str,
) -> None:
    provider = PiperTTSProvider((piper_model,))
    output = tmp_path / "final.wav"
    output.write_bytes(b"previous")
    token = CancellationToken()
    runtime.fail = mode == "failure"
    runtime.empty = mode == "empty"
    if mode == "cancelled":
        runtime.token = token
    expected = asyncio.CancelledError if mode == "cancelled" else PiperSynthesisError

    with pytest.raises(expected):
        asyncio.run(
            provider.synthesize(
                SynthesisRequest("Hello", "test-voice", "wav"), output, token
            )
        )

    assert output.read_bytes() == b"previous"
    assert not list(tmp_path.glob(".final.*.wav"))


def test_piper_reports_optional_runtime_missing(
    piper_model: PiperModel,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setitem(sys.modules, "piper", None)
    with pytest.raises(PiperSynthesisError, match="requirements-piper.txt"):
        asyncio.run(
            PiperTTSProvider((piper_model,)).synthesize(
                SynthesisRequest("Hello", "test-voice", "wav"), tmp_path / "final.wav"
            )
        )
    assert not (tmp_path / "final.wav").exists()


def test_piper_task_cancellation_waits_for_worker_cleanup(
    piper_model: PiperModel,
    runtime: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A cancelled awaiter must not leave a thread publishing audio afterward."""
    started = threading.Event()
    release = threading.Event()
    output = tmp_path / "final.wav"
    output.write_bytes(b"previous")
    provider = PiperTTSProvider((piper_model,))

    def blocked_synthesis(
        self: object, text: str, settings: object
    ) -> Iterator[SimpleNamespace]:
        started.set()
        assert release.wait(timeout=3)
        yield SimpleNamespace(audio_int16_bytes=b"\x01\x00" * 100)

    monkeypatch.setattr(
        sys.modules["piper"].PiperVoice, "synthesize", blocked_synthesis
    )

    async def exercise() -> None:
        task = asyncio.create_task(
            provider.synthesize(SynthesisRequest("Hello", "test-voice", "wav"), output)
        )
        try:
            assert await asyncio.to_thread(started.wait, 2)
            task.cancel()
            await asyncio.sleep(0)
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=3)
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())

    assert output.read_bytes() == b"previous"
    assert not list(tmp_path.glob(".final.*.wav"))


def test_piper_reuses_resident_model_but_revalidates_every_reload(
    piper_model: PiperModel, runtime: SimpleNamespace, tmp_path: Path
) -> None:
    provider = PiperTTSProvider((piper_model,))
    provider.prepare("test-voice")
    piper_model.model.path.write_bytes(b"changed after loading")
    asyncio.run(
        provider.synthesize(
            SynthesisRequest("Still resident", "test-voice", "wav"),
            tmp_path / "resident.wav",
        )
    )
    assert runtime.loads == 1
    provider.close()
    with pytest.raises(ModelValidationError, match="checksum mismatch"):
        provider.prepare("test-voice")
    assert runtime.loads == 1


def test_piper_load_rechecks_after_successful_prevalidation(
    piper_model: PiperModel,
) -> None:
    provider = PiperTTSProvider((piper_model,))
    provider.validate_configuration(SynthesisRequest("Hello", "test-voice", "wav"))
    piper_model.configuration.path.write_bytes(b"changed after validation")
    with pytest.raises(ModelValidationError, match="checksum mismatch"):
        provider.prepare("test-voice")


def test_piper_selects_speakers_without_reloading_shared_model(
    piper_model: PiperModel, runtime: SimpleNamespace, tmp_path: Path
) -> None:
    configuration = make_asset(
        tmp_path / "multi.json",
        json.dumps({"audio": {"sample_rate": 16000}, "num_speakers": 2}).encode(),
    )
    first = replace(piper_model, configuration=configuration, speaker_id=0)
    second = replace(
        first, voice=VoiceMetadata("second", "Second", "en-US"), speaker_id=1
    )
    provider = PiperTTSProvider((first, second))
    for model in (first, second, first):
        asyncio.run(
            provider.synthesize(
                SynthesisRequest("Hello", model.voice.voice_id, "wav"),
                tmp_path / "out.wav",
            )
        )
        assert runtime.speaker_id == model.speaker_id
    assert runtime.loads == 1
    provider.close()
    provider.prepare("second")
    assert runtime.loads == 2


@pytest.mark.parametrize("speaker_id", [None, -1, 2, True])
def test_piper_rejects_missing_or_out_of_range_speaker(
    piper_model: PiperModel, tmp_path: Path, speaker_id: int | None
) -> None:
    configuration = make_asset(
        tmp_path / "multi.json",
        json.dumps({"audio": {"sample_rate": 16000}, "num_speakers": 2}).encode(),
    )
    model = replace(piper_model, configuration=configuration, speaker_id=speaker_id)
    with pytest.raises(ModelValidationError, match="speaker"):
        PiperTTSProvider((model,)).validate_configuration(
            SynthesisRequest("Hello", "test-voice", "wav")
        )


def test_piper_model_switch_loads_only_selected_assets_and_releases_session(
    piper_model: PiperModel, runtime: SimpleNamespace, tmp_path: Path
) -> None:
    other = replace(
        piper_model,
        voice=VoiceMetadata("other", "Other", "en-GB"),
        model=make_asset(tmp_path / "other.onnx", b"other model"),
    )
    provider = PiperTTSProvider((piper_model, other))
    provider.prepare("test-voice")
    provider.prepare("other")
    provider.prepare("test-voice")
    assert runtime.loads == 3
    other.model.path.unlink()
    provider.prepare("test-voice")
    assert runtime.loads == 3
    with pytest.raises(ModelValidationError, match="Model library"):
        provider.prepare("other")


def test_piper_configuration_change_for_same_weights_reloads_session(
    piper_model: PiperModel, runtime: SimpleNamespace, tmp_path: Path
) -> None:
    second = replace(
        piper_model,
        voice=VoiceMetadata("second", "Second", "en-US"),
        configuration=make_asset(
            tmp_path / "multi.json",
            json.dumps({"audio": {"sample_rate": 16000}, "num_speakers": 2}).encode(),
        ),
        speaker_id=1,
    )
    provider = PiperTTSProvider((piper_model, second))
    provider.prepare("test-voice")
    provider.prepare("second")
    assert runtime.loads == 2
