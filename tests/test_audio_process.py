"""Child process error, timeout, and cancellation cleanup using the Python runtime."""

import asyncio
import subprocess
import sys
import threading

import pytest

from ttsapp import audio_process
from ttsapp.audio_combiner import FFmpegExecutionError, FFmpegNotFoundError
from ttsapp.audio_process import run_audio_process
from ttsapp.providers.base import CancellationToken
from ttsapp.workers import run_blocking_work


@pytest.fixture
def children(monkeypatch: pytest.MonkeyPatch) -> list[subprocess.Popen]:
    processes = []
    original = subprocess.Popen

    def create(*args: object, **kwargs: object) -> subprocess.Popen:
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(audio_process.subprocess, "Popen", create)
    return processes


def assert_reaped(children: list[subprocess.Popen]) -> None:
    assert children
    assert all(child.poll() is not None for child in children)
    assert all(child.stdout.closed and child.stderr.closed for child in children)


def test_process_reports_nonzero_exit_and_captured_reason(children) -> None:
    with pytest.raises(FFmpegExecutionError, match="codec failed"):
        run_audio_process(
            [
                sys.executable,
                "-c",
                "import sys\nsys.stderr.write('codec failed')\nsys.exit(2)",
            ],
            CancellationToken(),
        )
    assert_reaped(children)


def test_timeout_terminates_and_reaps_child(children) -> None:
    with pytest.raises(FFmpegExecutionError, match="timed out"):
        run_audio_process(
            [sys.executable, "-c", "import time\ntime.sleep(30)"],
            CancellationToken(),
            0.1,
        )
    assert_reaped(children)


def test_token_cancellation_terminates_and_reaps_child(children) -> None:
    token = CancellationToken()
    timer = threading.Timer(0.15, token.cancel)
    timer.start()
    try:
        with pytest.raises(asyncio.CancelledError):
            run_audio_process(
                [sys.executable, "-c", "import time\ntime.sleep(30)"], token
            )
    finally:
        timer.cancel()
    assert_reaped(children)


def test_async_task_cancellation_waits_for_process_cleanup(children) -> None:
    async def exercise() -> None:
        def operation(token: CancellationToken):
            return run_audio_process(
                [sys.executable, "-c", "import time\ntime.sleep(30)"], token
            )

        task = asyncio.create_task(run_blocking_work(operation, None))
        await asyncio.sleep(0.15)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=3)

    asyncio.run(exercise())
    assert_reaped(children)


def test_missing_audio_tool_is_actionable() -> None:
    with pytest.raises(FFmpegNotFoundError, match="Install FFmpeg and FFprobe"):
        run_audio_process(["missing-tts-audio-tool-for-test.exe"], CancellationToken())


def test_repeated_task_cancellation_still_waits_for_cleanup() -> None:
    started = threading.Event()
    release = threading.Event()
    cleaned = threading.Event()

    def operation(token: CancellationToken) -> None:
        started.set()
        assert release.wait(timeout=3)
        cleaned.set()
        token.raise_if_cancelled()

    async def exercise() -> None:
        task = asyncio.create_task(run_blocking_work(operation, None))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=3)
            assert cleaned.is_set()
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())
