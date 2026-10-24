"""Atomic disk-backed native audio writing shared by local synthesis engines."""

import os
import tempfile
import wave
from collections.abc import Iterable
from pathlib import Path

from .providers.base import CancellationToken


def write_pcm_wav(
    chunks: Iterable[bytes],
    output_file: Path,
    sample_rate: int,
    cancellation_token: CancellationToken,
) -> None:
    """Publish nonempty mono PCM16 WAV after all chunks complete successfully."""
    cancellation_token.raise_if_cancelled()
    if sample_rate <= 0:
        raise ValueError("Audio sample rate must be positive.")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{output_file.stem}.", suffix=".wav", dir=output_file.parent
    )
    os.close(descriptor)
    temporary = Path(name)
    try:
        with wave.open(str(temporary), "wb") as destination:
            destination.setnchannels(1)
            destination.setsampwidth(2)
            destination.setframerate(sample_rate)
            for chunk in chunks:
                cancellation_token.raise_if_cancelled()
                if len(chunk) % 2:
                    raise ValueError("PCM16 chunks must contain complete samples.")
                destination.writeframes(chunk)
        with wave.open(str(temporary), "rb") as result:
            if result.getnframes() == 0:
                raise ValueError("The provider produced empty audio.")
        cancellation_token.raise_if_cancelled()
        os.replace(temporary, output_file)
    finally:
        temporary.unlink(missing_ok=True)


def write_silence(
    output_file: Path,
    sample_rate: int,
    seconds: float,
    cancellation_token: CancellationToken,
) -> None:
    """Write a bounded, exact-duration PCM silence segment without a large buffer."""
    remaining = round(sample_rate * seconds)
    if remaining < 1:
        raise ValueError("Silence must contain at least one audio frame.")

    def chunks() -> Iterable[bytes]:
        nonlocal remaining
        while remaining:
            frames = min(remaining, sample_rate)
            yield b"\x00\x00" * frames
            remaining -= frames

    write_pcm_wav(chunks(), output_file, sample_rate, cancellation_token)
