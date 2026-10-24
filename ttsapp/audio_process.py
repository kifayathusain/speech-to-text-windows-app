"""Bounded, cancellable FFmpeg/FFprobe child processes without shell execution."""

import os
import subprocess
import time
from dataclasses import dataclass

from .audio_combiner import FFmpegExecutionError, FFmpegNotFoundError
from .providers.base import CancellationToken


@dataclass(frozen=True)
class AudioProcessResult:
    """Captured machine-readable output and actionable audio-tool diagnostics."""

    stdout: str
    stderr: str


def run_audio_process(
    command: list[str],
    cancellation_token: CancellationToken,
    timeout_seconds: float = 600,
) -> AudioProcessResult:
    """Run an audio tool, terminating and reaping it on cancellation or timeout."""
    cancellation_token.raise_if_cancelled()
    if not command or not command[0]:
        raise ValueError("Audio process command must identify an executable.")
    if timeout_seconds <= 0:
        raise ValueError("Audio processing timeout must be positive.")
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except FileNotFoundError as error:
        raise FFmpegNotFoundError(
            f"{command[0]} was not found on PATH. Install FFmpeg and FFprobe "
            "for validated exports."
        ) from error
    with process:
        try:
            while True:
                cancellation_token.raise_if_cancelled()
                remaining = timeout_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    raise FFmpegExecutionError("Audio processing timed out.")
                try:
                    stdout, stderr = process.communicate(timeout=min(0.1, remaining))
                except subprocess.TimeoutExpired:
                    continue
                if process.returncode != 0:
                    details = stderr.strip()[-4000:]
                    raise FFmpegExecutionError(
                        f"Audio processing failed (exit code {process.returncode}). "
                        f"{details}"
                    )
                cancellation_token.raise_if_cancelled()
                return AudioProcessResult(stdout, stderr)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
