"""Opt-in real codecs, loudness, mixed native layouts, and atomic export safety."""

import math
import os
import subprocess
import wave
from array import array
from pathlib import Path

import pytest

from ttsapp import audio_export
from ttsapp.audio_combiner import FFmpegExecutionError
from ttsapp.audio_export import ExportSettings, export_audio, probe_audio
from ttsapp.providers.base import CancellationToken

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("TTS_EXPORT_TESTS") != "1",
        reason="Set TTS_EXPORT_TESTS=1 with real FFmpeg and FFprobe on PATH.",
    ),
]


def tone(
    path: Path,
    rate: int = 16000,
    channels: int = 1,
    seconds: float = 1,
    amplitude: float = 0.1,
) -> None:
    samples = array("h")
    for index in range(round(rate * seconds)):
        value = round(32767 * amplitude * math.sin(2 * math.pi * 440 * index / rate))
        samples.extend([value] * channels)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(samples.tobytes())


@pytest.mark.parametrize(
    ("audio_format", "rate", "channels", "bitrate", "codec"),
    [
        ("wav", None, None, None, "pcm_s16le"),
        ("mp3", 44100, 2, 192, "mp3"),
        ("m4a", 24000, 1, None, "aac"),
    ],
)
def test_real_exports_normalize_mixed_layouts_and_validate_media(
    tmp_path: Path,
    audio_format: str,
    rate: int | None,
    channels: int | None,
    bitrate: int | None,
    codec: str,
) -> None:
    directory = tmp_path / "voice's café samples"
    directory.mkdir()
    first = directory / "first.wav"
    second = directory / "second.wav"
    tone(first, seconds=0.5)
    tone(second, rate=22050, channels=2, seconds=0.75)
    output = directory / f"final.{audio_format}"
    settings = ExportSettings(audio_format, bitrate, rate, channels)
    export_audio([first, second], output, settings, CancellationToken())
    info = probe_audio(output, CancellationToken())
    assert info.codec == codec
    assert info.sample_rate == (rate or 22050)
    assert info.channels == (channels or 2)
    assert abs(info.duration_seconds - 1.25) < 0.25
    assert not list(directory.glob(".export-*"))


def test_real_normalization_retains_native_rate_and_increases_quiet_levels(
    tmp_path: Path,
) -> None:
    source = tmp_path / "quiet.wav"
    tone(source, seconds=4, amplitude=0.01)
    output = tmp_path / "normalized.wav"
    export_audio(
        [source], output, ExportSettings("wav", normalize=True), CancellationToken()
    )
    with wave.open(str(output)) as audio:
        assert audio.getframerate() == 16000
        samples = array("h", audio.readframes(audio.getnframes()))
    assert max(abs(sample) for sample in samples) > 1000
    assert max(abs(sample) for sample in samples) < 32767
    assert not list(tmp_path.glob(".export-*"))


def test_native_mp3_copy_preserves_source_bitrate_without_reencoding(
    tmp_path: Path,
) -> None:
    source_wave = tmp_path / "source.wav"
    tone(source_wave, rate=24000, seconds=1)
    source = tmp_path / "source.mp3"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(source_wave), "-b:a", "48k", str(source)],
        check=True,
        capture_output=True,
    )
    output = tmp_path / "copied.mp3"
    export_audio([source, source], output, ExportSettings("mp3"), CancellationToken())
    assert probe_audio(output, CancellationToken()).bitrate == 48000


def test_validation_failure_preserves_prior_output_and_cleans_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.wav"
    tone(source)
    output = tmp_path / "final.wav"
    output.write_bytes(b"previous")

    def reject(*args: object) -> None:
        raise FFmpegExecutionError("Invalid final media")

    monkeypatch.setattr(audio_export, "_validate_output", reject)
    with pytest.raises(FFmpegExecutionError, match="Invalid final media"):
        export_audio(
            [source], output, ExportSettings("wav", overwrite=True), CancellationToken()
        )
    assert output.read_bytes() == b"previous"
    assert not list(tmp_path.glob(".export-*"))


def test_late_output_creation_is_not_overwritten_without_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if os.name != "nt":
        pytest.skip("Windows non-replacing rename semantics")
    source = tmp_path / "source.wav"
    tone(source)
    output = tmp_path / "final.wav"
    original_rename = os.rename

    def race(source_path: Path, destination: Path) -> None:
        output.write_bytes(b"another job")
        original_rename(source_path, destination)

    monkeypatch.setattr(audio_export.os, "rename", race)
    with pytest.raises(FileExistsError):
        export_audio([source], output, ExportSettings("wav"), CancellationToken())
    assert output.read_bytes() == b"another job"
    assert not list(tmp_path.glob(".export-*"))


def test_auto_mp3_bitrate_keeps_native_rate_and_uses_valid_codec_limit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.wav"
    tone(source)
    output = tmp_path / "auto.mp3"
    export_audio([source], output, ExportSettings("mp3"), CancellationToken())
    info = probe_audio(output, CancellationToken())
    assert info.sample_rate == 16000
    assert info.bitrate == 160000
    with pytest.raises(ValueError, match="at least 32000"):
        export_audio(
            [source],
            tmp_path / "invalid.mp3",
            ExportSettings("mp3", mp3_bitrate_kbps=320),
            CancellationToken(),
        )


def test_explicit_overwrite_publishes_valid_new_media(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    tone(source)
    output = tmp_path / "final.wav"
    output.write_bytes(b"previous")
    export_audio(
        [source], output, ExportSettings("wav", overwrite=True), CancellationToken()
    )
    assert probe_audio(output, CancellationToken()).codec == "pcm_s16le"
    assert not list(tmp_path.glob(".export-*"))


def test_completed_media_is_successful_when_only_cleanup_reports_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    original = audio_export.tempfile.TemporaryDirectory

    class CleanupFailure(original):
        def __exit__(self, *args: object) -> None:
            super().__exit__(*args)
            raise OSError("Cleanup reported a failure")

    monkeypatch.setattr(audio_export.tempfile, "TemporaryDirectory", CleanupFailure)
    source = tmp_path / "source.wav"
    tone(source)
    output = tmp_path / "final.wav"
    result = export_audio([source], output, ExportSettings("wav"), CancellationToken())
    assert result == output
    assert probe_audio(output, CancellationToken()).codec == "pcm_s16le"
    assert "Audio completed but export cleanup failed" in caplog.text
