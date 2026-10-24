"""Validated lossless-intermediate WAV/MP3/M4A export, separate from synthesis."""

import json
import logging
import math
import os
import tempfile
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .audio_combiner import FFmpegExecutionError, write_concat_file
from .audio_process import run_audio_process
from .providers.base import CancellationToken

OutputFormat = Literal["wav", "mp3", "m4a"]
ExportProgressCallback = Callable[[str], None]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportSettings:
    """Explicit output choices; None sample/channel/bitrate preserves source defaults."""

    audio_format: OutputFormat = "mp3"
    mp3_bitrate_kbps: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    normalize: bool = False
    overwrite: bool = False
    timeout_seconds: float = 600

    def __post_init__(self) -> None:
        if self.audio_format not in {"wav", "mp3", "m4a"}:
            raise ValueError("Export format must be WAV, MP3, or M4A.")
        if self.mp3_bitrate_kbps is not None and self.mp3_bitrate_kbps not in {
            64,
            96,
            128,
            160,
            192,
            256,
            320,
        }:
            raise ValueError("Unsupported MP3 bitrate.")
        if self.sample_rate is not None and self.sample_rate not in {
            16000,
            22050,
            24000,
            32000,
            44100,
            48000,
        }:
            raise ValueError("Unsupported export sample rate.")
        if self.channels not in {None, 1, 2}:
            raise ValueError("Export channels must be mono, stereo, or source default.")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("Export timeout must be finite and positive.")


@dataclass(frozen=True)
class AudioInfo:
    """Validated first-audio-stream metadata from FFprobe's JSON interface."""

    codec: str
    sample_rate: int
    channels: int
    duration_seconds: float
    container: str
    stream_count: int
    bitrate: int | None


def probe_audio(
    path: Path, cancellation_token: CancellationToken, timeout_seconds: float = 600
) -> AudioInfo:
    """Probe actual local media instead of assuming its extension proves its format."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Audio source is missing or empty: {path}")
    result = run_audio_process(
        [
            "ffprobe",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        cancellation_token,
        timeout_seconds,
    )
    try:
        metadata = json.loads(result.stdout)
        streams = metadata["streams"]
        stream = next(item for item in streams if item["codec_type"] == "audio")
        container = metadata["format"]
        container_name = str(container["format_name"])
        duration = float(stream.get("duration") or container["duration"])
        rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
        codec = str(stream["codec_name"])
        bitrate = int(stream["bit_rate"]) if stream.get("bit_rate") else None
        if not math.isfinite(duration) or duration <= 0 or rate <= 0 or channels <= 0:
            raise ValueError("Invalid audio stream metadata")
    except (ValueError, KeyError, TypeError, StopIteration) as error:
        raise FFmpegExecutionError(
            "FFprobe did not return valid audio metadata."
        ) from error
    return AudioInfo(
        codec, rate, channels, duration, container_name, len(streams), bitrate
    )


def _prepare_pcm_segments(
    audio_files: list[Path],
    infos: list[AudioInfo],
    directory: Path,
    sample_rate: int,
    channels: int,
    token: CancellationToken,
    timeout_seconds: float,
) -> tuple[list[Path], float]:
    prepared = []
    duration = 0.0
    for index, (source, info) in enumerate(zip(audio_files, infos, strict=True)):
        token.raise_if_cancelled()
        if (
            info.codec == "pcm_s16le"
            and info.sample_rate == sample_rate
            and info.channels == channels
            and "wav" in info.container.split(",")
        ):
            output = source
        else:
            output = directory / f"pcm_{index:05d}.wav"
            run_audio_process(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-i",
                    str(source),
                    "-map",
                    "0:a:0",
                    "-vn",
                    "-ac",
                    str(channels),
                    "-ar",
                    str(sample_rate),
                    "-c:a",
                    "pcm_s16le",
                    str(output),
                ],
                token,
                timeout_seconds,
            )
        with wave.open(str(output)) as audio:
            duration += audio.getnframes() / audio.getframerate()
        prepared.append(output)
    return prepared, duration


def _normalization_filter(
    input_arguments: list[str], token: CancellationToken, timeout_seconds: float
) -> str:
    """Measure the entire recording before applying bounded two-pass normalization."""
    result = run_audio_process(
        [
            "ffmpeg",
            "-nostdin",
            "-nostats",
            "-v",
            "info",
            *input_arguments,
            "-af",
            "loudnorm=I=-16:LRA=11:TP=-1.5:print_format=json",
            "-f",
            "null",
            "-",
        ],
        token,
        timeout_seconds,
    )
    try:
        start = result.stderr.rindex("{")
        measurements, _ = json.JSONDecoder().raw_decode(result.stderr[start:])
        fields = {
            "measured_I": "input_i",
            "measured_TP": "input_tp",
            "measured_LRA": "input_lra",
            "measured_thresh": "input_thresh",
            "offset": "target_offset",
        }
        values = {name: float(measurements[key]) for name, key in fields.items()}
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError("Cannot normalize silent or non-finite audio")
    except (ValueError, KeyError, TypeError) as error:
        raise FFmpegExecutionError(
            "Cannot obtain finite loudness measurements for normalization."
        ) from error
    parameters = ":".join(f"{name}={value}" for name, value in values.items())
    return f"loudnorm=I=-16:LRA=11:TP=-1.5:{parameters}:linear=true"


def _encoding_arguments(settings: ExportSettings, sample_rate: int) -> list[str]:
    if settings.audio_format == "wav":
        return ["-c:a", "pcm_s16le"]
    if settings.audio_format == "mp3":
        default_bitrate = 160 if sample_rate < 32000 else 192
        bitrate = settings.mp3_bitrate_kbps or default_bitrate
        return ["-c:a", "libmp3lame", "-b:a", f"{bitrate}k"]
    return ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-f", "ipod"]


def _validate_output(
    output: Path,
    settings: ExportSettings,
    sample_rate: int,
    channels: int,
    expected_duration: float,
    token: CancellationToken,
) -> None:
    info = probe_audio(output, token, settings.timeout_seconds)
    expected_codec = {"wav": "pcm_s16le", "mp3": "mp3", "m4a": "aac"}[
        settings.audio_format
    ]
    containers = set(info.container.split(","))
    expected_container = (
        "mov" if settings.audio_format == "m4a" else settings.audio_format
    )
    if (
        info.codec != expected_codec
        or expected_container not in containers
        or info.stream_count != 1
    ):
        raise FFmpegExecutionError(
            "Exported codec/container did not match the selected format."
        )
    if info.sample_rate != sample_rate or info.channels != channels:
        raise FFmpegExecutionError(
            "Exported sample rate/channels did not match configuration."
        )
    if abs(info.duration_seconds - expected_duration) > 0.25:
        raise FFmpegExecutionError(
            "Exported duration indicates unexpected truncation or padding."
        )
    if settings.audio_format == "mp3" and settings.mp3_bitrate_kbps is not None:
        expected_bitrate = settings.mp3_bitrate_kbps * 1000
        if (
            info.bitrate is None
            or abs(info.bitrate - expected_bitrate) > expected_bitrate * 0.05
        ):
            raise FFmpegExecutionError(
                "MP3 bitrate did not match the selected configuration."
            )
    run_audio_process(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(output),
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ],
        token,
        settings.timeout_seconds,
    )


def validate_export_target(final_audio: Path, settings: ExportSettings) -> None:
    """Validate format and explicit overwrite choice before synthesis side effects."""
    if final_audio.suffix.lower() != f".{settings.audio_format}":
        raise ValueError("Output extension must match the selected export format.")
    if final_audio.exists() and not settings.overwrite:
        raise FileExistsError(
            "Output already exists; explicitly choose overwrite or another file."
        )


def export_audio(
    audio_files: list[Path],
    final_audio: Path,
    settings: ExportSettings,
    cancellation_token: CancellationToken,
    *,
    on_progress: ExportProgressCallback | None = None,
) -> Path:
    """Normalize native inputs, validate final media, and publish with explicit overwrite."""
    token = cancellation_token
    token.raise_if_cancelled()
    if not audio_files:
        raise ValueError("At least one audio segment is required for export.")
    validate_export_target(final_audio, settings)
    if on_progress is not None:
        on_progress("Inspecting source audio...")
    infos = [probe_audio(path, token, settings.timeout_seconds) for path in audio_files]
    rate = settings.sample_rate or max(info.sample_rate for info in infos)
    channels = settings.channels or max(info.channels for info in infos)
    if (
        settings.audio_format == "mp3"
        and rate < 32000
        and (settings.mp3_bitrate_kbps or 0) > 160
    ):
        raise ValueError(
            "MP3 bitrates above 160 kbps require a sample rate of at least 32000 Hz."
        )
    copy_mp3 = (
        settings.audio_format == "mp3"
        and settings.mp3_bitrate_kbps is None
        and settings.sample_rate is None
        and settings.channels is None
        and not settings.normalize
        and all(
            info.codec == "mp3"
            and info.sample_rate == rate
            and info.channels == channels
            for info in infos
        )
    )
    final_audio.parent.mkdir(parents=True, exist_ok=True)
    committed = False
    try:
        with tempfile.TemporaryDirectory(
            prefix=".export-", dir=final_audio.parent
        ) as work:
            directory = Path(work)
            if copy_mp3:
                prepared = audio_files
                expected_duration = sum(info.duration_seconds for info in infos)
            else:
                if on_progress is not None:
                    on_progress("Preparing lossless audio...")
                prepared, expected_duration = _prepare_pcm_segments(
                    audio_files,
                    infos,
                    directory,
                    rate,
                    channels,
                    token,
                    settings.timeout_seconds,
                )
            concat_file = directory / "concat.txt"
            write_concat_file(prepared, concat_file)
            input_arguments = [
                "-protocol_whitelist",
                "file,pipe",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
            ]
            output = directory / f"completed.{settings.audio_format}"
            command = [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                *input_arguments,
                "-map",
                "0:a:0",
                "-vn",
            ]
            if copy_mp3:
                command.extend(["-c:a", "copy"])
            else:
                if settings.normalize:
                    if on_progress is not None:
                        on_progress("Normalizing loudness...")
                    command.extend(
                        [
                            "-af",
                            _normalization_filter(
                                input_arguments, token, settings.timeout_seconds
                            ),
                        ]
                    )
                command.extend(
                    [
                        "-ar",
                        str(rate),
                        "-ac",
                        str(channels),
                        *_encoding_arguments(settings, rate),
                    ]
                )
            command.append(str(output))
            if on_progress is not None:
                on_progress(f"Exporting {settings.audio_format.upper()}...")
            run_audio_process(command, token, settings.timeout_seconds)
            if on_progress is not None:
                on_progress("Checking final audio...")
            _validate_output(output, settings, rate, channels, expected_duration, token)
            token.raise_if_cancelled()
            if settings.overwrite:
                os.replace(output, final_audio)
            elif os.name == "nt":
                os.rename(output, final_audio)
            else:
                os.link(output, final_audio)
            committed = True
    except OSError as error:
        if not committed:
            raise
        logger.warning("Audio completed but export cleanup failed: %s", error)
    return final_audio
