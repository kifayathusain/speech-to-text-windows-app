"""FFmpeg adapter used to concatenate generated audio segments."""

import subprocess
from pathlib import Path
from typing import List


class FFmpegNotFoundError(RuntimeError):
    """Raised when the ``ffmpeg`` executable is not available on PATH."""


def write_concat_file(audio_files: List[Path], concat_file: Path) -> None:
    """Write an FFmpeg "concat demuxer" list file for ``audio_files``."""

    with open(concat_file, "w", encoding="utf-8") as file:
        for audio_file in audio_files:
            file.write(f"file '{audio_file.resolve().as_posix()}'\n")


def combine_audio(audio_files: List[Path], output_dir: Path, final_audio: Path) -> Path:
    """Concatenate ``audio_files`` (in order) into ``final_audio`` using FFmpeg."""

    concat_file = output_dir / "concat.txt"
    write_concat_file(audio_files, concat_file)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(final_audio),
            ],
            check=True,
        )
    except FileNotFoundError as error:
        raise FFmpegNotFoundError(
            "ffmpeg executable was not found on PATH. Install FFmpeg and "
            "ensure 'ffmpeg' is runnable from the command line."
        ) from error

    return final_audio
