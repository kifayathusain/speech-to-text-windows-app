"""FFmpeg adapter used to concatenate generated audio segments."""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List


class FFmpegNotFoundError(RuntimeError):
    """Raised when the ``ffmpeg`` executable is not available on PATH."""


class FFmpegExecutionError(RuntimeError):
    """Raised when FFmpeg cannot combine the generated audio segments."""


def _concat_path(audio_file: Path) -> str:
    """Return a concat-demuxer-safe, absolute path."""

    path = audio_file.resolve().as_posix()
    return path.replace("'", "'\\''")


def write_concat_file(audio_files: List[Path], concat_file: Path) -> None:
    """Write an FFmpeg "concat demuxer" list file for ``audio_files``."""

    with open(concat_file, "w", encoding="utf-8", newline="\n") as file:
        for audio_file in audio_files:
            file.write(f"file '{_concat_path(audio_file)}'\n")


def combine_audio(audio_files: List[Path], output_dir: Path, final_audio: Path) -> Path:
    """Concatenate ``audio_files`` in order, preserving any prior output on failure."""

    if not audio_files:
        raise ValueError("At least one audio segment is required for combination.")

    output_dir.mkdir(parents=True, exist_ok=True)
    final_audio.parent.mkdir(parents=True, exist_ok=True)

    concat_descriptor, concat_name = tempfile.mkstemp(
        prefix=".concat-", suffix=".txt", dir=str(output_dir)
    )
    concat_file = Path(concat_name)
    temporary_audio = None

    try:
        os.close(concat_descriptor)

        output_descriptor, output_name = tempfile.mkstemp(
            prefix=f".{final_audio.stem}.",
            suffix=final_audio.suffix or ".mp3",
            dir=str(final_audio.parent),
        )
        temporary_audio = Path(output_name)
        os.close(output_descriptor)

        write_concat_file(audio_files, concat_file)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-c",
                    "copy",
                    str(temporary_audio),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise FFmpegNotFoundError(
                "ffmpeg executable was not found on PATH. Install FFmpeg and "
                "ensure 'ffmpeg' is runnable from the command line."
            ) from error
        except subprocess.CalledProcessError as error:
            details = (error.stderr or "").strip()
            message = (
                "FFmpeg could not combine the audio segments "
                f"(exit code {error.returncode})."
            )
            if details:
                message = f"{message} {details}"
            raise FFmpegExecutionError(message) from error

        if (
            not temporary_audio.is_file()
            or temporary_audio.stat().st_size == 0
        ):
            raise FFmpegExecutionError(
                "FFmpeg completed without producing a non-empty audio file."
            )

        os.replace(temporary_audio, final_audio)
        return final_audio
    finally:
        concat_file.unlink(missing_ok=True)
        if temporary_audio is not None:
            temporary_audio.unlink(missing_ok=True)
