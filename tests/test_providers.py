"""Provider selection, configuration, routing, and cancellation behavior."""

import asyncio
from pathlib import Path

import pytest

from ttsapp import service, tts_engine
from ttsapp.providers.base import (
    CancellationToken,
    ProviderCapabilities,
    SynthesisRequest,
    SynthesisResult,
)
from ttsapp.providers.edge import EdgeTTSProvider
from ttsapp.providers.registry import ProviderRegistry, create_default_registry


def test_registry_discovers_default_edge_and_rejects_unknown_provider() -> None:
    registry = create_default_registry()
    provider = registry.get("edge")

    assert registry.list_providers() == (provider,)
    assert provider.get_capabilities().online
    assert not provider.get_capabilities().requires_model
    assert provider.get_capabilities().audio_formats == ("mp3",)
    assert {voice.voice_id for voice in provider.get_available_voices()} == {
        "en-GB-SoniaNeural",
        "en-GB-RyanNeural",
    }
    with pytest.raises(ValueError, match="Unknown TTS provider"):
        registry.get("missing")


def test_registry_rejects_duplicate_provider_id() -> None:
    registry = create_default_registry()

    with pytest.raises(ValueError, match="already registered"):
        registry.register(EdgeTTSProvider())


@pytest.mark.parametrize("identifier", ["", " ", " edge", "edge "])
def test_registry_rejects_invalid_provider_id(identifier: str) -> None:
    provider = EdgeTTSProvider()
    provider.provider_id = identifier

    with pytest.raises(ValueError, match="Provider ID"):
        ProviderRegistry().register(provider)


@pytest.mark.parametrize(
    ("synthesis_request", "message"),
    [
        (SynthesisRequest(" ", "voice"), "text cannot be empty"),
        (SynthesisRequest("Hello", " "), "voice must be selected"),
        (SynthesisRequest("Hello", "voice", audio_format="wav"), "native MP3"),
        (SynthesisRequest("Hello", "voice", speed=1.2), "speed is not supported"),
        (
            SynthesisRequest("Hello", "en-GB-SoniaNeural", language="fr-FR"),
            "language must match",
        ),
    ],
)
def test_edge_rejects_unsupported_configuration(
    synthesis_request: SynthesisRequest,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        EdgeTTSProvider().validate_configuration(synthesis_request)


def test_edge_accepts_custom_voice_and_matching_locale() -> None:
    EdgeTTSProvider().validate_configuration(
        SynthesisRequest("Hello", "en-US-JennyNeural", language="en-US")
    )


def test_service_rejects_unknown_provider_before_output_creation(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="Unknown TTS provider"):
        asyncio.run(
            service.generate_conversation(
                input_text="Caller: Hello",
                provider_id="unknown",
                output_dir=tmp_path / "parts",
            )
        )

    assert list(tmp_path.iterdir()) == []


class RecordingProvider(EdgeTTSProvider):
    """Test provider independent of the actual network/Edge synthesis adapter."""

    provider_id = "recording"

    def __init__(self) -> None:
        self.requests: list[SynthesisRequest] = []

    async def synthesize(
        self,
        request: SynthesisRequest,
        output_file: Path,
        cancellation_token: CancellationToken | None = None,
    ) -> SynthesisResult:
        self.requests.append(request)
        output_file.write_bytes(request.text.encode())
        return SynthesisResult(output_file, "mp3")


def test_service_uses_injected_provider_for_every_segment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = RecordingProvider()
    final_audio = tmp_path / "final.mp3"

    def combine(files: list[Path], parts: Path, output: Path) -> Path:
        output.write_bytes(b"|".join(file.read_bytes() for file in files))
        return output

    monkeypatch.setattr(service.audio_combiner, "combine_audio", combine)

    result = asyncio.run(
        service.generate_conversation(
            input_text="Caller: Café\nCaller: Goodbye",
            output_dir=tmp_path / "parts",
            final_audio=final_audio,
            provider_id="recording",
            provider=provider,
        )
    )

    assert result == final_audio
    assert [request.text for request in provider.requests] == ["Café", "Goodbye"]
    assert final_audio.read_bytes() == "Café|Goodbye".encode()


def test_service_rejects_mismatched_injected_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must match"):
        asyncio.run(
            service.generate_conversation(
                input_text="Caller: Hello",
                output_dir=tmp_path / "parts",
                provider=RecordingProvider(),
            )
        )

    assert list(tmp_path.iterdir()) == []


def test_service_validates_all_provider_requests_before_output_creation(
    tmp_path: Path,
) -> None:
    class RejectingProvider(RecordingProvider):
        def validate_configuration(self, request: SynthesisRequest) -> None:
            if request.text == "Invalid":
                raise ValueError("Invalid configuration")

    provider = RejectingProvider()
    with pytest.raises(ValueError, match="Invalid configuration"):
        asyncio.run(
            service.generate_conversation(
                input_text="Caller: Valid\nCaller: Invalid",
                output_dir=tmp_path / "parts",
                provider_id=provider.provider_id,
                provider=provider,
            )
        )

    assert provider.requests == []
    assert list(tmp_path.iterdir()) == []


def test_service_rejects_unimplemented_native_format_before_writing(
    tmp_path: Path,
) -> None:
    class UnsupportedProvider(RecordingProvider):
        def get_capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(online=False, audio_formats=("ogg",))

    with pytest.raises(ValueError, match="requires native MP3"):
        asyncio.run(
            service.generate_conversation(
                input_text="Caller: Hello",
                output_dir=tmp_path / "parts",
                provider_id="recording",
                provider=UnsupportedProvider(),
            )
        )

    assert list(tmp_path.iterdir()) == []


def test_precancelled_service_creates_no_output(tmp_path: Path) -> None:
    token = CancellationToken()
    token.cancel()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            service.generate_conversation(
                input_text="Caller: Hello",
                output_dir=tmp_path / "parts",
                cancellation_token=token,
            )
        )

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("cancel_task", [False, True])
def test_edge_live_cancellation_cleans_partial_output_and_preserves_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cancel_task: bool,
) -> None:
    output = tmp_path / "final.mp3"
    output.write_bytes(b"previous")
    token = CancellationToken()

    async def exercise() -> None:
        started = asyncio.Event()

        class SlowCommunicate:
            def __init__(self, text: str, voice: str) -> None:
                pass

            async def save(self, path: str) -> None:
                Path(path).write_bytes(b"partial")
                started.set()
                await asyncio.sleep(10)

        monkeypatch.setattr(tts_engine.edge_tts, "Communicate", SlowCommunicate)
        synthesis = asyncio.create_task(
            EdgeTTSProvider().synthesize(
                SynthesisRequest("Hello", "voice"), output, token
            )
        )
        await asyncio.wait_for(started.wait(), timeout=2)
        if cancel_task:
            synthesis.cancel()
        else:
            token.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(synthesis, timeout=2)

    asyncio.run(exercise())

    assert output.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [output]


def test_edge_checks_cancellation_before_atomic_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = CancellationToken()
    output = tmp_path / "final.mp3"
    output.write_bytes(b"previous")

    class CancellingCommunicate:
        def __init__(self, text: str, voice: str) -> None:
            pass

        async def save(self, path: str) -> None:
            Path(path).write_bytes(b"complete but cancelled")
            token.cancel()

    monkeypatch.setattr(tts_engine.edge_tts, "Communicate", CancellingCommunicate)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            EdgeTTSProvider().synthesize(
                SynthesisRequest("Hello", "voice"), output, token
            )
        )

    assert output.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [output]
