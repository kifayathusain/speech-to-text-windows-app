"""Native WAV export validation without requiring an installed FFmpeg binary."""

import subprocess
import wave
from pathlib import Path

import pytest

from ttsapp.audio_combiner import combine_audio


def write_wav(path: Path, sample_rate: int = 16000) -> None:
    """Create a tiny valid PCM segment."""
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x01\x00" * 100)


@pytest.mark.parametrize(
    ("suffix", "codec"), [(".mp3", "libmp3lame"), (".wav", "pcm_s16le")]
)
def test_native_wav_uses_explicit_output_encoding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
    codec: str,
) -> None:
    source = tmp_path / "source.wav"
    write_wav(source)
    output = tmp_path / f"final{suffix}"

    def encode(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        assert command[command.index("-c") + 1] == codec
        Path(command[-1]).write_bytes(b"encoded")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("ttsapp.audio_combiner.subprocess.run", encode)

    combine_audio([source], tmp_path, output, source_format="wav")

    assert output.read_bytes() == b"encoded"
    assert set(tmp_path.iterdir()) == {source, output}


def test_native_wav_rejects_sample_rate_mismatch_before_replacing_output(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    write_wav(first)
    write_wav(second, 22050)
    output = tmp_path / "final.mp3"
    output.write_bytes(b"previous")

    with pytest.raises(ValueError, match="matching sample rates"):
        combine_audio([first, second], tmp_path, output, source_format="wav")

    assert output.read_bytes() == b"previous"
