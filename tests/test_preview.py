"""Selected-voice previews, cache validity, cancellation, and playback flags."""

import asyncio
import sys
from pathlib import Path
from types import ModuleType

import pytest

from ttsapp.audio_files import write_pcm_wav
from ttsapp.preview import (
    SAMPLE_TEXT,
    PreviewService,
    WindowsAudioPlayer,
    build_preview_text,
    strip_speaker_labels,
)
from ttsapp.providers.base import (
    CancellationToken,
    ProviderCapabilities,
    SynthesisRequest,
    SynthesisResult,
    VoiceMetadata,
)


class PreviewProvider:
    """Deterministic PCM synthesis with observable selected voice/speed requests."""

    provider_id = "test"
    display_name = "Test"

    def __init__(self) -> None:
        self.requests: list[SynthesisRequest] = []
        self.cancel = False
        self.fail = False

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            online=False, audio_formats=("wav",), supports_speed=True
        )

    def get_available_voices(self) -> tuple[VoiceMetadata, ...]:
        return (VoiceMetadata("one", "One", "en-US"),)

    def validate_configuration(self, request: SynthesisRequest) -> None:
        assert request.audio_format == "wav"

    async def synthesize(
        self,
        request: SynthesisRequest,
        output_file: Path,
        cancellation_token: CancellationToken | None = None,
    ) -> SynthesisResult:
        self.requests.append(request)
        if self.cancel:
            raise asyncio.CancelledError
        if self.fail:
            raise RuntimeError("Preview synthesis failed")
        write_pcm_wav(
            (b"\x01\x00" * 100,),
            output_file,
            24000,
            cancellation_token or CancellationToken(),
        )
        return SynthesisResult(output_file, "wav")

    def close(self) -> None:
        """The controlled provider retains no resources."""


class PreviewSource:
    """Provide explicit model identity without depending on real model files."""

    def __init__(self, provider: PreviewProvider) -> None:
        self.provider = provider
        self.identity = "test-model-v1"

    def get(self, provider_id: str) -> PreviewProvider:
        assert provider_id == "test"
        return self.provider

    def cache_identity(self, provider_id: str) -> str:
        return self.identity


def test_preview_uses_selected_voice_speed_and_reuses_matching_cache(
    tmp_path: Path,
) -> None:
    provider = PreviewProvider()
    source = PreviewSource(provider)
    previews = PreviewService(source, tmp_path)
    first = asyncio.run(previews.generate("test", "one", "Selected text.", 0.8))
    repeated = asyncio.run(previews.generate("test", "one", "Selected text.", 0.8))
    assert repeated == first
    assert len(provider.requests) == 1
    assert provider.requests[0].text == "Selected text."
    assert provider.requests[0].voice_id == "one"
    assert provider.requests[0].speed == 0.8
    faster = asyncio.run(previews.generate("test", "one", "Selected text.", 1.2))
    source.identity = "test-model-v2"
    changed_model = asyncio.run(previews.generate("test", "one", "Selected text.", 1.2))
    changed_voice = asyncio.run(previews.generate("test", "two", "Selected text.", 1.2))
    assert len({first, faster, changed_model, changed_voice}) == 4


def test_preview_cache_is_bounded_and_preserves_unrelated_files(tmp_path: Path) -> None:
    unrelated = tmp_path / "personal.wav"
    unrelated.write_bytes(b"unrelated")
    provider = PreviewProvider()
    previews = PreviewService(PreviewSource(provider), tmp_path, max_entries=2)
    for text in ("First", "Second", "Third", "Fourth"):
        asyncio.run(previews.generate("test", "one", text))
    assert len(list(tmp_path.glob("*.wav"))) == 3
    assert unrelated.read_bytes() == b"unrelated"
    assert not list(tmp_path.glob(".preview-*"))


@pytest.mark.parametrize("cancel", [False, True])
def test_failed_preview_preserves_previous_cache_and_removes_temporary_files(
    tmp_path: Path, cancel: bool
) -> None:
    provider = PreviewProvider()
    previews = PreviewService(PreviewSource(provider), tmp_path)
    previous = asyncio.run(previews.generate("test", "one", "Previous"))
    provider.cancel = cancel
    provider.fail = not cancel
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        asyncio.run(previews.generate("test", "one", "New text"))
    assert previous.is_file()
    assert not list(tmp_path.glob(".preview-*"))
    assert list(tmp_path.glob("*.wav")) == [previous]


def test_corrupted_cache_is_regenerated(tmp_path: Path) -> None:
    provider = PreviewProvider()
    previews = PreviewService(PreviewSource(provider), tmp_path)
    cached = asyncio.run(previews.generate("test", "one", "Hello"))
    cached.write_bytes(b"corrupted")
    assert asyncio.run(previews.generate("test", "one", "Hello")) == cached
    assert len(provider.requests) == 2


def test_precancelled_preview_does_not_create_cache(tmp_path: Path) -> None:
    token = CancellationToken()
    token.cancel()
    previews = PreviewService(PreviewSource(PreviewProvider()), tmp_path / "cache")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(previews.generate("test", "one", None, cancellation_token=token))
    assert list(tmp_path.iterdir()) == []


def test_preview_text_is_bounded_and_preserves_nonlabel_colons() -> None:
    assert build_preview_text(None) == SAMPLE_TEXT
    assert len(build_preview_text("Long text " * 100)) <= 400
    assert (
        strip_speaker_labels("Caller: Meet at 9:30.\nTime: unchanged", {"Caller"})
        == " Meet at 9:30.\nTime: unchanged"
    )


def test_windows_playback_is_async_and_stop_uses_native_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, int]] = []
    winsound = ModuleType("winsound")
    winsound.SND_FILENAME = 1
    winsound.SND_ASYNC = 2
    winsound.SND_NODEFAULT = 4
    winsound.PlaySound = lambda source, flags: calls.append((source, flags))
    monkeypatch.setitem(sys.modules, "winsound", winsound)
    player = WindowsAudioPlayer()
    player.play(Path("voice.wav"))
    player.stop()
    assert calls == [("voice.wav", 7), (None, 0)]
