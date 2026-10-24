"""Optional CPU-only Piper inference using explicitly verified voice assets."""

from __future__ import annotations

import json
import math
import threading
import wave
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from ..audio_files import write_pcm_wav
from ..models.assets import ModelAsset, ModelValidationError
from ..workers import run_blocking_work
from .base import (
    CancellationToken,
    ProviderCapabilities,
    SynthesisRequest,
    SynthesisResult,
    VoiceMetadata,
)
from .onnx_sessions import create_cpu_session

if TYPE_CHECKING:
    from piper import PiperVoice


class PiperSynthesisError(RuntimeError):
    """Piper could not load its runtime or synthesize the requested audio."""


@dataclass(frozen=True)
class PiperModel:
    """One known voice with verified model/configuration and licensing metadata."""

    voice: VoiceMetadata
    model: ModelAsset
    configuration: ModelAsset


class PiperTTSProvider:
    """Lazy, serialized CPU synthesis with a single reusable model session."""

    provider_id = "piper"
    display_name = "Piper (offline CPU)"

    def __init__(
        self,
        models: tuple[PiperModel, ...],
        cpu_threads: int = 4,
        memory_arena: bool = True,
    ) -> None:
        if cpu_threads < 1:
            raise ValueError("CPU thread count must be positive.")
        self._cpu_threads = cpu_threads
        self._memory_arena = memory_arena
        self._models: dict[str, PiperModel] = {}
        for model in models:
            identifier = model.voice.voice_id
            if not identifier or identifier in self._models:
                raise ValueError("Piper voice IDs must be nonempty and unique.")
            self._models[identifier] = model
        self._lock = threading.Lock()
        self._loaded_voice_id: str | None = None
        self._voice: PiperVoice | None = None

    def get_capabilities(self) -> ProviderCapabilities:
        """Advertise native WAV, CPU model requirements, and cooperative controls."""
        return ProviderCapabilities(
            online=False,
            audio_formats=("wav",),
            supports_speed=True,
            requires_model=True,
            requires_download=True,
        )

    def get_available_voices(self) -> tuple[VoiceMetadata, ...]:
        """Discover configured voices without scanning or loading unknown assets."""
        return tuple(model.voice for model in self._models.values())

    def validate_configuration(self, request: SynthesisRequest) -> None:
        """Reject invalid settings or corrupted assets before inference starts."""
        if not request.text.strip():
            raise ValueError("Speech text cannot be empty.")
        if request.voice_id not in self._models:
            raise ModelValidationError(f"Unknown Piper voice: '{request.voice_id}'.")
        if request.audio_format != "wav":
            raise ValueError("Piper produces native WAV audio; export separately.")
        if request.speed is not None and (
            not math.isfinite(request.speed) or request.speed <= 0
        ):
            raise ValueError("Speaking speed must be a finite positive number.")
        model = self._models[request.voice_id]
        if request.language is not None and request.language != model.voice.language:
            raise ValueError("Piper language must match the selected voice.")
        if self._loaded_voice_id != request.voice_id:
            self._validate_model(model)

    def _validate_model(self, model: PiperModel) -> None:
        """Verify the complete model/configuration before a runtime is loaded."""
        model.model.validate()
        model.configuration.validate()
        try:
            configuration = json.loads(model.configuration.path.read_text("utf-8"))
            phoneme_type = configuration.get("phoneme_type", "espeak")
            sample_rate = configuration["audio"]["sample_rate"]
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise ModelValidationError("Invalid Piper voice configuration.") from error
        if phoneme_type != "espeak":
            raise ModelValidationError(
                "Only bundled eSpeak phonemization is supported; no extra downloads."
            )
        if not isinstance(sample_rate, int) or sample_rate <= 0:
            raise ModelValidationError("Piper sample rate must be a positive integer.")

    def _load_voice(self, model: PiperModel) -> PiperVoice:
        """Load CPU inference only on first use or an explicit voice change."""
        if self._loaded_voice_id != model.voice.voice_id:
            self._validate_model(model)
            try:
                from piper import PiperConfig, PiperVoice

                session = create_cpu_session(
                    model.model.path, self._cpu_threads, self._memory_arena
                )
            except ImportError as error:
                raise PiperSynthesisError(
                    "Install optional CPU dependencies from requirements-piper.txt."
                ) from error
            self._voice = None
            self._loaded_voice_id = None
            configuration = json.loads(model.configuration.path.read_text("utf-8"))
            voice = PiperVoice(
                session=session,
                config=PiperConfig.from_dict(configuration),
                use_tashkeel=False,
            )
            self._voice = voice
            self._loaded_voice_id = model.voice.voice_id
        assert self._voice is not None
        return self._voice

    def prepare(self, voice_id: str) -> None:
        """Explicitly verify/load a voice for measured startup or loading progress."""
        with self._lock:
            if voice_id not in self._models:
                raise ModelValidationError(f"Unknown Piper voice: '{voice_id}'.")
            model = self._models[voice_id]
            self._load_voice(model)

    async def synthesize(
        self,
        request: SynthesisRequest,
        output_file: Path,
        cancellation_token: CancellationToken | None = None,
    ) -> SynthesisResult:
        """Run inference off the event loop; finish cleanup before cancellation exits."""
        return await run_blocking_work(
            partial(self._synthesize_sync, request, output_file), cancellation_token
        )

    def _synthesize_sync(
        self,
        request: SynthesisRequest,
        output_file: Path,
        token: CancellationToken,
    ) -> SynthesisResult:
        """Write disk-backed sentence chunks and atomically publish a valid WAV."""
        with self._lock:
            token.raise_if_cancelled()
            self.validate_configuration(request)
            try:
                voice = self._load_voice(self._models[request.voice_id])
                from piper import SynthesisConfig

                settings = SynthesisConfig(
                    length_scale=1.0 / (request.speed or 1.0), normalize_audio=False
                )
                chunks = (
                    chunk.audio_int16_bytes
                    for chunk in voice.synthesize(request.text, settings)
                )
                write_pcm_wav(chunks, output_file, voice.config.sample_rate, token)
            except (
                ImportError,
                OSError,
                RuntimeError,
                ValueError,
                wave.Error,
            ) as error:
                if isinstance(error, PiperSynthesisError):
                    raise
                raise PiperSynthesisError(
                    f"Piper CPU synthesis failed: {error}"
                ) from error
        return SynthesisResult(output_file, "wav")

    def close(self) -> None:
        """Release the retained inference session after any running job finishes."""
        with self._lock:
            self._voice = None
            self._loaded_voice_id = None
