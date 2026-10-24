"""Atomic native WAV safety shared by both offline engines."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest

from ttsapp.audio_files import write_pcm_wav
from ttsapp.providers.base import CancellationToken


@pytest.mark.parametrize("mode", ["empty", "unaligned", "failure", "cancellation"])
def test_native_wav_failure_preserves_output_and_cleans_temporary_files(
    tmp_path: Path, mode: str
) -> None:
    output = tmp_path / "final.wav"
    output.write_bytes(b"previous")
    token = CancellationToken()

    def chunks() -> Iterator[bytes]:
        if mode == "empty":
            return
        if mode == "unaligned":
            yield b"\x01"
            return
        yield b"\x01\x00" * 10
        if mode == "failure":
            raise ValueError("Inference failed")
        token.cancel()

    expected = asyncio.CancelledError if mode == "cancellation" else ValueError
    with pytest.raises(expected):
        write_pcm_wav(chunks(), output, 24000, token)

    assert output.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [output]
