"""Windows desktop UI for the TTS app (M02).

Built with Tkinter (part of the Python standard library, no extra
dependency needed) so the app can run as a plain desktop window without a
developer workflow.

The UI only handles input collection, validation, threading and rendering
progress/results. All TTS/FFmpeg work is delegated to
:func:`ttsapp.service.generate_conversation`, so this module does not
duplicate any pipeline logic.

Plain functions (``validate_script_text``, ``build_speaker_voice_mapping``) are
kept free of Tkinter so they can be unit tested without a display.
"""

import asyncio
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, Optional

from .audio_combiner import FFmpegExecutionError, FFmpegNotFoundError
from .config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_FINAL_AUDIO,
    DEFAULT_OUTPUT_DIR,
    VOICES,
)
from .parser import ConversationLine
from .service import generate_conversation
from .tts_engine import TTSGenerationError

APP_TITLE = f"{APP_NAME} {APP_VERSION}"


def default_desktop_output_path() -> Path:
    """Return a writable, predictable output location independent of the CWD."""

    return Path.home() / "Documents" / APP_NAME / DEFAULT_FINAL_AUDIO


def format_generation_error(error: Exception) -> str:
    """Add plain-language recovery steps to common generation errors."""

    if isinstance(error, FFmpegNotFoundError):
        return (
            "FFmpeg is required to combine the generated speech. Install FFmpeg, "
            "add ffmpeg.exe to PATH, then restart the app. Verify the installation "
            "with `ffmpeg -version`."
        )
    if isinstance(error, FFmpegExecutionError):
        return (
            "The speech was generated, but FFmpeg could not combine the audio. "
            "Check that FFmpeg is installed and that the generated files are "
            "available, then try again.\n\n"
            f"Details: {error}"
        )
    if isinstance(error, PermissionError):
        return (
            "The app could not save to the selected location. Choose a folder "
            "where your account has write permission.\n\n"
            f"Details: {error}"
        )
    if isinstance(error, TTSGenerationError):
        return (
            "Speech generation failed. Check your internet connection and the "
            "selected Edge TTS voice, then try again.\n\n"
            f"Details: {error}"
        )
    return str(error)


def validate_script_text(text: str) -> None:
    """Raise ``ValueError`` if ``text`` has no usable conversation content."""

    if not text or not text.strip():
        raise ValueError("Please enter or paste some conversation text first.")


def build_speaker_voice_mapping(
    speaker_rows: list[tuple[str, str]],
) -> Dict[str, str]:
    """Validate editable speaker names and their selected Edge TTS voices."""

    voices = {}
    for index, (speaker, voice) in enumerate(speaker_rows, start=1):
        speaker = speaker.strip()
        voice = voice.strip()
        if not speaker and not voice:
            continue
        if not speaker:
            raise ValueError(f"Please enter a name for Speaker {index}.")
        if not voice:
            raise ValueError(f"Please enter an Edge TTS voice for '{speaker}'.")
        if speaker in voices:
            raise ValueError(f"Speaker name '{speaker}' is used more than once.")
        voices[speaker] = voice

    if not voices:
        raise ValueError("Configure at least one speaker name and voice.")

    return voices


class _ProgressMessage:
    """Internal message passed from the worker thread to the UI thread."""

    def __init__(self, kind: str, **data):
        self.kind = kind  # "progress" | "success" | "error"
        self.data = data


class TTSDesktopApp(tk.Tk):
    """Main application window.

    Generation runs on a background thread (with its own asyncio event
    loop) so the Tkinter mainloop/UI never blocks while Edge TTS/FFmpeg are
    working. The worker thread never touches Tkinter widgets directly; it
    posts messages onto a thread-safe queue that is drained periodically on
    the UI thread via ``after()``.
    """

    POLL_INTERVAL_MS = 100

    def __init__(self) -> None:
        super().__init__()

        self.title(APP_TITLE)
        self.geometry("680x600")
        self.minsize(600, 500)

        self._voices = dict(VOICES)
        self._speaker_rows: list[tuple[tk.StringVar, tk.StringVar]] = []
        self._output_path_var = tk.StringVar(
            value=str(default_desktop_output_path())
        )
        self._status_var = tk.StringVar(value="Ready.")
        self._queue: "queue.Queue[_ProgressMessage]" = queue.Queue()
        self._worker: Optional[threading.Thread] = None

        self._build_widgets()
        self.after(self.POLL_INTERVAL_MS, self._drain_queue)

    # -- UI construction ---------------------------------------------------

    def _build_widgets(self) -> None:
        padding = {"padx": 10, "pady": 6}

        text_label = ttk.Label(
            self,
            text=(
                "Conversation script (one line per entry, formatted as "
                "'Speaker: text'):"
            ),
        )
        text_label.pack(anchor="w", **padding)
        ttk.Label(
            self,
            text="Requires an internet connection and FFmpeg installed on PATH.",
        ).pack(anchor="w", padx=10)

        text_frame = ttk.Frame(self)
        text_frame.pack(fill="both", expand=True, padx=10)

        self.text_box = tk.Text(text_frame, wrap="word", height=14, undo=True)
        scrollbar = ttk.Scrollbar(text_frame, command=self.text_box.yview)
        self.text_box.configure(yscrollcommand=scrollbar.set)
        self.text_box.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._voices_frame = ttk.LabelFrame(
            self, text="Speaker and voice mapping"
        )
        self._voices_frame.pack(fill="x", **padding)
        ttk.Label(
            self._voices_frame,
            text="Speaker names must match the labels before ':' in the script.",
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(4, 6))
        ttk.Label(self._voices_frame, text="Slot").grid(
            row=1, column=0, sticky="w", padx=(8, 4), pady=4
        )
        ttk.Label(self._voices_frame, text="Script speaker name").grid(
            row=1, column=1, sticky="w", padx=(0, 4), pady=4
        )
        ttk.Label(self._voices_frame, text="Edge TTS voice").grid(
            row=1, column=2, sticky="w", padx=(0, 8), pady=4
        )
        for row, (speaker, voice) in enumerate(self._voices.items(), start=1):
            speaker_var = tk.StringVar(value=speaker)
            voice_var = tk.StringVar(value=voice)
            self._speaker_rows.append((speaker_var, voice_var))
            ttk.Label(self._voices_frame, text=f"Speaker {row}").grid(
                row=row + 1, column=0, sticky="w", padx=(8, 4), pady=4
            )
            ttk.Entry(self._voices_frame, textvariable=speaker_var, width=20).grid(
                row=row + 1, column=1, sticky="w", padx=(0, 4), pady=4
            )
            ttk.Entry(self._voices_frame, textvariable=voice_var, width=30).grid(
                row=row + 1, column=2, sticky="w", padx=(0, 8), pady=4
            )

        output_frame = ttk.Frame(self)
        output_frame.pack(fill="x", **padding)

        ttk.Label(output_frame, text="Output file:").pack(side="left")
        ttk.Entry(output_frame, textvariable=self._output_path_var).pack(
            side="left", fill="x", expand=True, padx=(6, 6)
        )
        ttk.Button(output_frame, text="Browse...", command=self._choose_output_path).pack(
            side="left"
        )

        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", **padding)

        self.generate_button = ttk.Button(
            action_frame, text="Generate", command=self._on_generate_clicked
        )
        self.generate_button.pack(side="left")

        self.progress_bar = ttk.Progressbar(
            action_frame, mode="determinate", maximum=1, value=0
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(10, 0))

        status_label = ttk.Label(self, textvariable=self._status_var, anchor="w")
        status_label.pack(fill="x", padx=10, pady=(0, 10))

    # -- Event handlers ------------------------------------------------------

    def _choose_output_path(self) -> None:
        chosen = filedialog.asksaveasfilename(
            title="Choose output audio file",
            defaultextension=".mp3",
            filetypes=[("MP3 audio", "*.mp3"), ("All files", "*.*")],
            initialfile=Path(self._output_path_var.get()).name,
        )
        if chosen:
            self._output_path_var.set(chosen)

    def _on_generate_clicked(self) -> None:
        script_text = self.text_box.get("1.0", "end")

        try:
            validate_script_text(script_text)
            voices = build_speaker_voice_mapping(
                [(speaker.get(), voice.get()) for speaker, voice in self._speaker_rows]
            )
        except ValueError as error:
            messagebox.showerror(APP_TITLE, str(error))
            return

        final_audio = Path(
            self._output_path_var.get().strip() or str(default_desktop_output_path())
        )
        output_dir = final_audio.parent / DEFAULT_OUTPUT_DIR.name

        self._set_busy(True)
        self._status_var.set("Generating...")
        self.progress_bar.configure(value=0, maximum=1)

        self._worker = threading.Thread(
            target=self._run_generation,
            args=(script_text, output_dir, final_audio, voices),
            daemon=True,
        )
        self._worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.generate_button.configure(state="disabled" if busy else "normal")

    # -- Background worker (runs off the UI thread) -------------------------

    def _run_generation(
        self,
        script_text: str,
        output_dir: Path,
        final_audio: Path,
        voices: Dict[str, str],
    ) -> None:
        def on_progress(index: int, total: int, line: ConversationLine) -> None:
            self._queue.put(
                _ProgressMessage("progress", index=index, total=total, speaker=line.speaker)
            )

        try:
            result = asyncio.run(
                generate_conversation(
                    output_dir=output_dir,
                    final_audio=final_audio,
                    voices=voices,
                    on_progress=on_progress,
                    input_text=script_text,
                )
            )
            self._queue.put(_ProgressMessage("success", final_audio=result))
        except Exception as error:  # noqa: BLE001 - surface any failure to the UI
            self._queue.put(
                _ProgressMessage("error", message=format_generation_error(error))
            )

    # -- UI-thread queue draining --------------------------------------------

    def _drain_queue(self) -> None:
        try:
            while True:
                message = self._queue.get_nowait()
                self._handle_message(message)
        except queue.Empty:
            pass
        finally:
            self.after(self.POLL_INTERVAL_MS, self._drain_queue)

    def _handle_message(self, message: _ProgressMessage) -> None:
        if message.kind == "progress":
            index = message.data["index"]
            total = message.data["total"]
            speaker = message.data["speaker"]
            self.progress_bar.configure(maximum=total, value=index)
            self._status_var.set(f"[{index}/{total}] Generated line for {speaker}...")
        elif message.kind == "success":
            final_audio = message.data["final_audio"]
            self._set_busy(False)
            self._status_var.set(f"Done. Saved to: {final_audio}")
            messagebox.showinfo(APP_TITLE, f"Final audio created:\n{final_audio}")
        elif message.kind == "error":
            self._set_busy(False)
            error_message = message.data["message"]
            self._status_var.set("Generation failed. See the error message.")
            messagebox.showerror(APP_TITLE, error_message)


def main() -> None:
    app = TTSDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
