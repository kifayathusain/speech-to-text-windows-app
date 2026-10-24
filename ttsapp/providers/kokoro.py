"""Optional Kokoro-82M ONNX provider for explicitly selected offline CPU voices."""

from __future__ import annotations

import math
import sys
import threading
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
    from kokoro_onnx import Kokoro
    from numpy import ndarray


class KokoroSynthesisError(RuntimeError):
    """Kokoro's optional runtime or native synthesis could not complete."""


@dataclass(frozen=True)
class KokoroModel:
    """Verified ONNX/voice files with an explicit supported voice inventory."""

    model: ModelAsset
    voice_data: ModelAsset
    voices: tuple[VoiceMetadata, ...]


class KokoroTTSProvider:
    """Lazy, reusable, CPU-only inference with bounded per-request audio."""

    provider_id = "kokoro"
    display_name = "Kokoro-82M (offline CPU)"
    max_text_characters = 2000

    def __init__(
        self, model: KokoroModel, cpu_threads: int = 4, memory_arena: bool = False
    ) -> None:
        if cpu_threads < 1:
            raise ValueError("CPU thread count must be positive.")
        self._model = model
        self._voices = {voice.voice_id: voice for voice in model.voices}
        if not self._voices or len(self._voices) != len(model.voices):
            raise ValueError("Kokoro requires a nonempty, unique voice inventory.")
        self._cpu_threads = cpu_threads
        self._memory_arena = memory_arena
        self._lock = threading.Lock()
        self._engine: Kokoro | None = None
        self._voice_styles: dict[str, ndarray] = {}

    def get_capabilities(self) -> ProviderCapabilities:
        """Describe native PCM output and the currently supported controls."""
        return ProviderCapabilities(
            online=False,
            audio_formats=("wav",),
            supports_speed=True,
            requires_model=True,
            requires_download=True,
            max_text_characters=self.max_text_characters,
        )

    def get_available_voices(self) -> tuple[VoiceMetadata, ...]:
        """Return catalog metadata without loading the ONNX or voice archive."""
        return tuple(self._voices.values())

    def validate_configuration(self, request: SynthesisRequest) -> None:
        """Validate bounded input, voice settings, and trusted local assets."""
        if not request.text.strip():
            raise ValueError("Speech text cannot be empty.")
        if len(request.text) > self.max_text_characters:
            raise ValueError("Kokoro segments must not exceed 2000 characters.")
        if request.voice_id not in self._voices:
            raise ModelValidationError(f"Unknown Kokoro voice: '{request.voice_id}'.")
        if request.audio_format != "wav":
            raise ValueError("Kokoro produces native WAV audio; export separately.")
        if request.speed is not None and (
            not math.isfinite(request.speed) or not 0.5 <= request.speed <= 2.0
        ):
            raise ValueError("Kokoro speaking speed must be between 0.5 and 2.0.")
        voice = self._voices[request.voice_id]
        if request.language is not None and request.language != voice.language:
            raise ValueError("Kokoro language must match the selected voice.")
        # Loaded weights and styles are resident, verified data. Reloads always
        # recheck full hashes, including after close or a model-library change.
        if self._engine is None:
            self._model.model.validate()
            self._model.voice_data.validate()

    def _load_engine(self) -> Kokoro:
        """Create one explicit CPU session without allowing an online fallback."""
        if self._engine is None:
            self._model.model.validate()
            self._model.voice_data.validate()
            if not (3, 10) <= sys.version_info[:2] < (3, 14):
                raise KokoroSynthesisError(
                    "Kokoro ONNX requires Python 3.10–3.13; Edge remains available."
                )
            try:
                from kokoro_onnx import Kokoro

                session = create_cpu_session(
                    self._model.model.path, self._cpu_threads, self._memory_arena
                )
            except ImportError as error:
                raise KokoroSynthesisError(
                    "Install optional CPU dependencies from requirements-kokoro.txt."
                ) from error
            engine = Kokoro.from_session(session, str(self._model.voice_data.path))
            try:
                available = set(engine.get_voices())
                if not set(self._voices).issubset(available):
                    raise ModelValidationError(
                        "Kokoro voice archive lacks catalog voices."
                    )
                styles = {}
                for identifier in self._voices:
                    style = engine.get_voice_style(identifier).copy()
                    style.setflags(write=False)
                    styles[identifier] = style
            finally:
                engine.voices.close()
            self._voice_styles = styles
            self._engine = engine
        return self._engine

    def prepare(self) -> None:
        """Explicitly verify/load assets when a caller needs loading progress."""
        with self._lock:
            self._load_engine()

    async def synthesize(
        self,
        request: SynthesisRequest,
        output_file: Path,
        cancellation_token: CancellationToken | None = None,
    ) -> SynthesisResult:
        """Generate a bounded native segment without blocking the caller's loop."""
        return await run_blocking_work(
            partial(self._synthesize_sync, request, output_file), cancellation_token
        )

    def _synthesize_sync(
        self,
        request: SynthesisRequest,
        output_file: Path,
        token: CancellationToken,
    ) -> SynthesisResult:
        """Run one job at a time and atomically publish finite PCM samples."""
        with self._lock:
            token.raise_if_cancelled()
            self.validate_configuration(request)
            try:
                engine = self._load_engine()
                import numpy as np

                token.raise_if_cancelled()
                voice = self._voices[request.voice_id]
                audio, sample_rate = engine.create(
                    request.text,
                    voice=self._voice_styles[request.voice_id],
                    speed=request.speed or 1.0,
                    lang=voice.language.lower(),
                )
                token.raise_if_cancelled()
                if not np.isfinite(audio).all():
                    raise KokoroSynthesisError("Kokoro produced invalid audio samples.")
                pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()
                write_pcm_wav((pcm,), output_file, sample_rate, token)
            except (ImportError, OSError, RuntimeError, ValueError) as error:
                if isinstance(error, KokoroSynthesisError):
                    raise
                raise KokoroSynthesisError(
                    f"Kokoro CPU synthesis failed: {error}"
                ) from error
        return SynthesisResult(output_file, "wav")

    def close(self) -> None:
        """Release resident voice styles and the retained ONNX session."""
        with self._lock:
            if self._engine is not None:
                self._engine = None
            self._voice_styles.clear()
