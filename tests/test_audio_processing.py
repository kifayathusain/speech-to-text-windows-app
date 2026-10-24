"""Lossless intermediate conversion and cancellation at the final commit point."""

import asyncio
import subprocess
import wave
from pathlib import Path

import pytest

from ttsapp.audio_combiner import combine_audio, decode_to_wav
from ttsapp.audio_process import AudioProcessResult
from ttsapp.providers.base import CancellationToken


def write_pcm(path: Path) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x01\x00" * 100)


def test_decode_writes_valid_pcm_without_upsampling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "native.mp3"
    source.write_bytes(b"native")
    output = tmp_path / "decoded.wav"

    def decode(command: list[str], token: CancellationToken) -> AudioProcessResult:
        assert "-ar" not in command
        assert command[command.index("-c:a") + 1] == "pcm_s16le"
        write_pcm(Path(command[-1]))
        return AudioProcessResult("", "")

    monkeypatch.setattr("ttsapp.audio_process.run_audio_process", decode)
    decode_to_wav(source, output, CancellationToken())

    with wave.open(str(output)) as audio:
        assert audio.getframerate() == 16000
    assert set(tmp_path.iterdir()) == {source, output}


def test_cancelled_export_preserves_previous_media_and_removes_temporary_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.wav"
    write_pcm(source)
    output = tmp_path / "final.mp3"
    output.write_bytes(b"previous")
    token = CancellationToken()

    def encode(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        Path(command[-1]).write_bytes(b"new media")
        token.cancel()
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("ttsapp.audio_combiner.subprocess.run", encode)

    with pytest.raises(asyncio.CancelledError):
        combine_audio(
            [source], tmp_path, output, source_format="wav", cancellation_token=token
        )

    assert output.read_bytes() == b"previous"
    assert set(tmp_path.iterdir()) == {source, output}
