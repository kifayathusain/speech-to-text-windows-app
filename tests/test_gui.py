"""Tests for the non-Tkinter logic in the desktop UI module.

These test the plain functions ``validate_script_text`` and
``build_speaker_voice_mapping`` directly, without constructing any Tkinter
widgets, so they run headless in CI without a display.
"""

import asyncio
import queue
import threading

import pytest

from ttsapp import gui
from ttsapp.audio_combiner import FFmpegExecutionError, FFmpegNotFoundError
from ttsapp.gui import (
    TTSDesktopApp,
    build_speaker_voice_mapping,
    default_desktop_output_path,
    format_generation_error,
    validate_script_text,
)
from ttsapp.tts_engine import TTSGenerationError


def test_validate_script_text_rejects_empty_string():
    with pytest.raises(ValueError):
        validate_script_text("")


def test_validate_script_text_rejects_whitespace_only():
    with pytest.raises(ValueError):
        validate_script_text("   \n\n  ")


def test_validate_script_text_accepts_real_content():
    # Should not raise.
    validate_script_text("Receptionist: Hello there.\n")


def test_build_speaker_voice_mapping_accepts_custom_names():
    assert build_speaker_voice_mapping(
        [("Doctor", " en-US-JennyNeural "), ("Nurse", "en-US-GuyNeural")]
    ) == {
        "Doctor": "en-US-JennyNeural",
        "Nurse": "en-US-GuyNeural",
    }


def test_build_speaker_voice_mapping_allows_an_unused_blank_slot():
    assert build_speaker_voice_mapping(
        [("Doctor", "en-US-JennyNeural"), ("", "")]
    ) == {"Doctor": "en-US-JennyNeural"}


@pytest.mark.parametrize(
    ("speaker_rows", "error"),
    [
        ([("", "en-US-JennyNeural")], "name for Speaker 1"),
        ([("Doctor", " ")], "voice for 'Doctor'"),
        (
            [("Doctor", "en-US-JennyNeural"), ("Doctor", "en-US-GuyNeural")],
            "used more than once",
        ),
    ],
)
def test_build_speaker_voice_mapping_rejects_invalid_rows(speaker_rows, error):
    with pytest.raises(ValueError, match=error):
        build_speaker_voice_mapping(speaker_rows)


def test_default_desktop_output_path_uses_documents_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(gui.Path, "home", lambda: tmp_path)

    assert default_desktop_output_path() == (
        tmp_path / "Documents" / "Windows TTS App" / "conversation.mp3"
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            FFmpegNotFoundError("not found"),
            "Install FFmpeg, add ffmpeg.exe to PATH",
        ),
        (
            FFmpegExecutionError("invalid audio"),
            "Check that FFmpeg is installed and that the generated files are available",
        ),
        (
            TTSGenerationError("connection timed out"),
            "Check your internet connection and the selected Edge TTS voice",
        ),
        (
            PermissionError("access denied"),
            "Choose a folder where your account has write permission",
        ),
    ],
)
def test_format_generation_error_includes_recovery_steps(error, expected):
    assert expected in format_generation_error(error)


def test_generate_click_runs_work_in_background_and_updates_ui_from_queue(
    monkeypatch, tmp_path
):
    generation_started = threading.Event()
    allow_generation_to_finish = threading.Event()
    main_thread = threading.current_thread()
    ui_thread_calls = []

    async def slow_generation(**kwargs):
        assert kwargs["voices"] == {
            "Doctor": "en-US-JennyNeural",
            "Nurse": "en-US-GuyNeural",
        }
        generation_started.set()
        await asyncio.to_thread(allow_generation_to_finish.wait, 5)
        return kwargs["final_audio"]

    class Value:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            ui_thread_calls.append(threading.current_thread())
            self.value = value

    class Button:
        def configure(self, **kwargs):
            ui_thread_calls.append(threading.current_thread())
            self.state = kwargs["state"]

    class Progress:
        def configure(self, **kwargs):
            ui_thread_calls.append(threading.current_thread())

    class TextBox:
        def get(self, start, end):
            return "Doctor: Hello"

    app = TTSDesktopApp.__new__(TTSDesktopApp)
    app.text_box = TextBox()
    app._output_path_var = Value(str(tmp_path / "exports" / "final.mp3"))
    app._speaker_rows = [
        (Value("Doctor"), Value("en-US-JennyNeural")),
        (Value("Nurse"), Value("en-US-GuyNeural")),
    ]
    app._status_var = Value("Ready.")
    app.generate_button = Button()
    app.progress_bar = Progress()
    app._queue = queue.Queue()
    app._worker = None
    monkeypatch.setattr(gui, "generate_conversation", slow_generation)
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *args: None)

    try:
        app._on_generate_clicked()
        assert generation_started.wait(timeout=2)
        assert app._worker is not None and app._worker.is_alive()
        assert app._status_var.value == "Generating..."
        assert app.generate_button.state == "disabled"
        assert ui_thread_calls == [main_thread] * 3

        allow_generation_to_finish.set()
        app._worker.join(timeout=2)
        assert not app._worker.is_alive()
        assert ui_thread_calls == [main_thread] * 3

        message = app._queue.get_nowait()
        assert message.kind == "success"
        app._handle_message(message)
        assert app.generate_button.state == "normal"
        assert app._status_var.value.endswith(str(tmp_path / "exports" / "final.mp3"))
        assert ui_thread_calls == [main_thread] * 5
    finally:
        allow_generation_to_finish.set()
        if app._worker is not None:
            app._worker.join(timeout=2)
