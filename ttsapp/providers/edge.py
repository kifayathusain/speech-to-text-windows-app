"""Microsoft Edge provider preserving the existing atomic synthesis adapter."""

import asyncio
from pathlib import Path

from .. import tts_engine
from ..config import VOICES
from .base import (
    CancellationToken,
    ProviderCapabilities,
    SynthesisRequest,
    SynthesisResult,
    VoiceMetadata,
)


class EdgeTTSProvider:
    """Online provider; no local model or inference runtime is required."""

    provider_id = "edge"
    display_name = "Microsoft Edge TTS (online)"

    def close(self) -> None:
        """Edge retains no local inference session between synthesis requests."""

    def get_capabilities(self) -> ProviderCapabilities:
        """Expose controls implemented by this adapter, rather than upstream APIs."""
        return ProviderCapabilities(online=True, audio_formats=("mp3",))

    def get_available_voices(self) -> tuple[VoiceMetadata, ...]:
        """Return configured defaults; additional Edge voice IDs remain accepted."""
        return tuple(
            VoiceMetadata(voice, speaker, "-".join(voice.split("-")[:2]))
            for speaker, voice in VOICES.items()
        )

    def validate_configuration(self, request: SynthesisRequest) -> None:
        """Validate supported settings without making a network request."""
        if not request.text or not request.text.strip():
            raise ValueError("Speech text cannot be empty.")
        if not request.voice_id or not request.voice_id.strip():
            raise ValueError("An Edge TTS voice must be selected.")
        if request.audio_format != "mp3":
            raise ValueError("Edge TTS produces native MP3 audio; export separately.")
        if request.speed is not None:
            raise ValueError("Speaking speed is not supported by the Edge adapter.")
        if request.language is not None:
            voice_language = "-".join(request.voice_id.split("-")[:2])
            if request.language.casefold() != voice_language.casefold():
                raise ValueError("Edge language must match the selected voice locale.")

    async def synthesize(
        self,
        request: SynthesisRequest,
        output_file: Path,
        cancellation_token: CancellationToken | None = None,
    ) -> SynthesisResult:
        """Synthesize through the legacy adapter with optional live cancellation."""
        self.validate_configuration(request)
        if cancellation_token is None:
            await tts_engine.synthesize_line(
                request.text, request.voice_id, output_file
            )
            return SynthesisResult(output_file, "mp3")

        cancellation_token.raise_if_cancelled()
        synthesis = asyncio.create_task(
            tts_engine.synthesize_line(
                request.text,
                request.voice_id,
                output_file,
                cancellation_token=cancellation_token,
            )
        )
        cancellation = asyncio.create_task(cancellation_token.wait())
        try:
            completed, _ = await asyncio.wait(
                (synthesis, cancellation), return_when=asyncio.FIRST_COMPLETED
            )
            if synthesis in completed:
                await synthesis
                return SynthesisResult(output_file, "mp3")
            raise asyncio.CancelledError
        finally:
            synthesis.cancel()
            cancellation.cancel()
            await asyncio.gather(synthesis, cancellation, return_exceptions=True)
