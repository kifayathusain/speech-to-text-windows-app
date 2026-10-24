"""Export option validation and FFprobe error handling without external tools."""

import json
from pathlib import Path

import pytest

from ttsapp import audio_export
from ttsapp.audio_combiner import FFmpegExecutionError
from ttsapp.audio_export import ExportSettings, export_audio, probe_audio
from ttsapp.audio_process import AudioProcessResult
from ttsapp.desktop_options import build_export_settings
from ttsapp.providers.base import CancellationToken


@pytest.mark.parametrize(
    "settings",
    [
        {"audio_format": "ogg"},
        {"mp3_bitrate_kbps": 12},
        {"sample_rate": 12345},
        {"channels": 3},
        {"timeout_seconds": 0},
        {"timeout_seconds": float("nan")},
    ],
)
def test_invalid_export_configuration_is_rejected(settings: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ExportSettings(**settings)


def test_desktop_export_choices_are_explicit_and_non_mp3_ignores_bitrate() -> None:
    settings = build_export_settings("m4a", "unused", "24000", "Stereo", True)
    assert settings.audio_format == "m4a"
    assert settings.mp3_bitrate_kbps is None
    assert settings.sample_rate == 24000
    assert settings.channels == 2
    assert settings.normalize
    assert not settings.overwrite


def test_existing_output_requires_explicit_overwrite_before_source_processing(
    tmp_path: Path,
) -> None:
    output = tmp_path / "final.wav"
    output.write_bytes(b"previous")
    with pytest.raises(FileExistsError, match="explicitly choose overwrite"):
        export_audio(
            [tmp_path / "missing.wav"],
            output,
            ExportSettings("wav"),
            CancellationToken(),
        )
    assert output.read_bytes() == b"previous"
    assert not list(tmp_path.glob(".export-*"))


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"streams": [], "format": {}},
        {"streams": [{"codec_type": "audio", "sample_rate": "0"}], "format": {}},
    ],
)
def test_malformed_probe_metadata_is_actionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, metadata: dict
) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(b"controlled input")
    monkeypatch.setattr(
        audio_export,
        "run_audio_process",
        lambda *args: AudioProcessResult(json.dumps(metadata), ""),
    )
    with pytest.raises(FFmpegExecutionError, match="valid audio metadata"):
        probe_audio(source, CancellationToken())


def test_silent_normalization_is_rejected_instead_of_generating_invalid_gain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statistics = {
        "input_i": "-inf",
        "input_tp": "-inf",
        "input_lra": "0",
        "input_thresh": "-70",
        "target_offset": "inf",
    }
    monkeypatch.setattr(
        audio_export,
        "run_audio_process",
        lambda *args: AudioProcessResult("", json.dumps(statistics)),
    )
    with pytest.raises(FFmpegExecutionError, match="finite loudness"):
        audio_export._normalization_filter([], CancellationToken(), 1)
