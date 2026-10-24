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
import os
import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass, replace
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .audio_combiner import FFmpegExecutionError, FFmpegNotFoundError
from .audio_export import validate_export_target
from .config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_FINAL_AUDIO,
    DEFAULT_OUTPUT_DIR,
    VOICES,
)
from .desktop_options import (
    DesktopGenerationOptions,
    build_desktop_options,
    build_export_settings,
)
from .model_library import ModelLibraryWindow
from .parser import ConversationLine
from .preview import PreviewService, WindowsAudioPlayer, strip_speaker_labels
from .provider_manager import ProviderManager
from .providers.base import CancellationToken
from .service import generate_conversation
from .text_processing import SpeechChunk
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
            "with `ffmpeg -version`. Validated exports also require ffprobe.exe "
            "on PATH."
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
) -> dict[str, str]:
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


@dataclass(frozen=True)
class _ProgressMessage:
    """Internal message passed from the worker thread to the UI thread."""

    kind: str
    index: int = 0
    total: int = 0
    speaker: str = ""
    final_audio: Path | None = None
    path: Path | None = None
    revision: int = 0
    message: str = ""


class TTSDesktopApp(tk.Tk):
    """Tkinter input/rendering with worker-owned synthesis, previews, and sessions."""

    POLL_INTERVAL_MS = 100

    def __init__(self, providers: ProviderManager | None = None) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("800x760")
        self.minsize(720, 620)
        self._provider_manager = (
            providers if providers is not None else ProviderManager()
        )
        self._choices = {
            choice.provider_id: choice
            for choice in self._provider_manager.list_choices()
        }
        self._choice_names = {
            choice.display_name: choice.provider_id for choice in self._choices.values()
        }
        self._provider_id = "edge"
        self._provider_var = tk.StringVar(value=self._choices["edge"].display_name)
        self._language_var = tk.StringVar(value="All languages")
        self._provider_status = tk.StringVar()
        self._speed_var = tk.StringVar(value="1.0")
        self._process_text_var = tk.BooleanVar(value=False)
        self._edge_processing = False
        self._sentence_pause_var = tk.StringVar(value="0.0")
        self._paragraph_pause_var = tk.StringVar(value="0.35")
        self._format_var = tk.StringVar(value="MP3")
        self._bitrate_var = tk.StringVar(value="Auto")
        self._sample_rate_var = tk.StringVar(value="Native")
        self._channels_var = tk.StringVar(value="Source")
        self._normalize_var = tk.BooleanVar(value=False)
        self._speaker_rows: list[tuple[tk.StringVar, tk.StringVar]] = []
        self._speaker_entries: list[ttk.Entry] = []
        self._voice_boxes: list[ttk.Combobox] = []
        self._preview_buttons: list[ttk.Button] = []
        self._voice_selections: dict[str, tuple[str, ...]] = {}
        self._output_path_var = tk.StringVar(value=str(default_desktop_output_path()))
        self._status_var = tk.StringVar(value="Ready.")
        self._count_var = tk.StringVar(value="0 words · 0 characters")
        self._elapsed_var = tk.StringVar(value="")
        self._queue: queue.Queue[_ProgressMessage] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._model_library: ModelLibraryWindow | None = None
        self._cancellation_token = CancellationToken()
        self._preview_service = PreviewService(self._provider_manager)
        self._player = WindowsAudioPlayer()
        self._last_preview: Path | None = None
        self._preview_revision = 0
        self._busy = False
        self._closing = False
        self._shutdown_started = False
        self._operation_kind = ""
        self._started_at = 0.0
        self._chunk_progress_active = False
        self._exporting = False
        self._build_widgets()
        self._provider_changed()
        self._speed_var.trace_add("write", lambda *args: self._invalidate_preview())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(self.POLL_INTERVAL_MS, self._drain_queue)

    def _build_widgets(self) -> None:
        self._build_text_editor()
        self._build_provider_controls()
        self._build_speaker_controls()
        self._build_processing_controls()
        self._build_export_controls()
        self._build_output_controls()
        self._build_actions()

    def _build_text_editor(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=6)
        ttk.Label(toolbar, text="Conversation script: Speaker: text").pack(side="left")
        ttk.Button(toolbar, text="Paste", command=self._paste_text).pack(
            side="left", padx=8
        )
        ttk.Button(
            toolbar, text="Clear", command=lambda: self.text_box.delete("1.0", "end")
        ).pack(side="left")
        ttk.Label(toolbar, textvariable=self._count_var).pack(side="right")
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10)
        self.text_box = tk.Text(frame, wrap="word", height=10, undo=True)
        scrollbar = ttk.Scrollbar(frame, command=self.text_box.yview)
        self.text_box.configure(yscrollcommand=scrollbar.set)
        self.text_box.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.text_box.bind("<<Modified>>", self._text_modified)

    def _build_provider_controls(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=10, pady=6)
        ttk.Label(frame, text="Provider:").pack(side="left")
        self._provider_box = ttk.Combobox(
            frame,
            textvariable=self._provider_var,
            values=tuple(self._choice_names),
            state="readonly",
            width=22,
        )
        self._provider_box.pack(side="left", padx=6)
        self._provider_box.bind(
            "<<ComboboxSelected>>", lambda event: self._provider_changed()
        )
        ttk.Label(frame, text="Language/accent:").pack(side="left")
        self._language_box = ttk.Combobox(
            frame, textvariable=self._language_var, state="readonly", width=14
        )
        self._language_box.pack(side="left", padx=6)
        self._language_box.bind(
            "<<ComboboxSelected>>", lambda event: self._filter_voices()
        )
        self._model_library_button = ttk.Button(
            frame, text="Model library...", command=self._open_model_library
        )
        self._model_library_button.pack(side="right")
        ttk.Label(self, textvariable=self._provider_status, wraplength=760).pack(
            fill="x", padx=10
        )

    def _build_speaker_controls(self) -> None:
        frame = ttk.LabelFrame(self, text="Speakers and voices")
        frame.pack(fill="x", padx=10, pady=6)
        for index, (speaker, voice) in enumerate(VOICES.items()):
            speaker_var = tk.StringVar(value=speaker)
            voice_var = tk.StringVar(value=voice)
            self._speaker_rows.append((speaker_var, voice_var))
            ttk.Label(frame, text=f"Speaker {index + 1}").grid(
                row=index, column=0, padx=6, pady=4
            )
            entry = ttk.Entry(frame, textvariable=speaker_var, width=20)
            entry.grid(row=index, column=1, padx=4, pady=4, sticky="ew")
            self._speaker_entries.append(entry)
            voice_box = ttk.Combobox(frame, textvariable=voice_var, width=29)
            voice_box.grid(row=index, column=2, padx=4, pady=4, sticky="ew")
            self._voice_boxes.append(voice_box)
            button = ttk.Button(
                frame,
                text="Preview",
                command=lambda slot=index: self._on_preview_clicked(slot),
            )
            button.grid(row=index, column=3, padx=6, pady=4)
            self._preview_buttons.append(button)
            voice_var.trace_add("write", lambda *args: self._invalidate_preview())
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=2)
        ttk.Label(
            self,
            text="Select text and click a speaker's Preview, or preview a sample (up to 400 characters).",
        ).pack(anchor="w", padx=10)

    def _build_processing_controls(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=10, pady=6)
        ttk.Label(frame, text="Speed:").pack(side="left")
        self._speed_control = ttk.Spinbox(
            frame,
            textvariable=self._speed_var,
            from_=0.5,
            to=2.0,
            increment=0.1,
            width=5,
        )
        self._speed_control.pack(side="left", padx=5)
        self._process_control = ttk.Checkbutton(
            frame,
            text="Process text / pauses",
            variable=self._process_text_var,
            command=self._apply_control_states,
        )
        self._process_control.pack(side="left", padx=6)
        ttk.Label(frame, text="Sentence pause (s):").pack(side="left")
        self._sentence_control = ttk.Spinbox(
            frame,
            textvariable=self._sentence_pause_var,
            from_=0,
            to=5,
            increment=0.05,
            width=5,
        )
        self._sentence_control.pack(side="left", padx=5)
        ttk.Label(frame, text="Paragraph (s):").pack(side="left")
        self._paragraph_control = ttk.Spinbox(
            frame,
            textvariable=self._paragraph_pause_var,
            from_=0,
            to=5,
            increment=0.05,
            width=5,
        )
        self._paragraph_control.pack(side="left", padx=5)

    def _build_export_controls(self) -> None:
        frame = ttk.LabelFrame(self, text="Audio export")
        frame.pack(fill="x", padx=10, pady=4)
        ttk.Label(frame, text="Format:").grid(row=0, column=0, padx=6, pady=4)
        self._format_box = ttk.Combobox(
            frame,
            textvariable=self._format_var,
            values=("MP3", "WAV", "M4A"),
            width=7,
            state="readonly",
        )
        self._format_box.grid(row=0, column=1, padx=4, pady=4)
        self._format_box.bind(
            "<<ComboboxSelected>>", lambda event: self._export_format_changed()
        )
        ttk.Label(frame, text="MP3 bitrate (kbps):").grid(row=0, column=2, padx=6)
        self._bitrate_box = ttk.Combobox(
            frame,
            textvariable=self._bitrate_var,
            values=("Auto", "64", "96", "128", "160", "192", "256", "320"),
            width=8,
            state="readonly",
        )
        self._bitrate_box.grid(row=0, column=3, padx=4)
        self._normalize_control = ttk.Checkbutton(
            frame, text="Normalize loudness", variable=self._normalize_var
        )
        self._normalize_control.grid(row=0, column=4, padx=10)
        ttk.Label(frame, text="Sample rate:").grid(row=1, column=0, padx=6, pady=4)
        self._sample_rate_box = ttk.Combobox(
            frame,
            textvariable=self._sample_rate_var,
            values=("Native", "16000", "22050", "24000", "32000", "44100", "48000"),
            width=7,
            state="readonly",
        )
        self._sample_rate_box.grid(row=1, column=1, padx=4, pady=4)
        ttk.Label(frame, text="Channels:").grid(row=1, column=2, padx=6)
        self._channels_box = ttk.Combobox(
            frame,
            textvariable=self._channels_var,
            values=("Source", "Mono", "Stereo"),
            width=8,
            state="readonly",
        )
        self._channels_box.grid(row=1, column=3, padx=4)

    def _export_format_changed(self) -> None:
        output = self._output_path_var.get().strip() or str(
            default_desktop_output_path()
        )
        self._output_path_var.set(
            str(Path(output).with_suffix(f".{self._format_var.get().lower()}"))
        )
        self._apply_control_states()

    def _build_output_controls(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=10, pady=6)
        ttk.Label(frame, text="Output file:").pack(side="left")
        ttk.Entry(frame, textvariable=self._output_path_var).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(frame, text="Browse...", command=self._choose_output_path).pack(
            side="left"
        )
        ttk.Button(frame, text="Open folder", command=self._open_output_folder).pack(
            side="left", padx=6
        )

    def _build_actions(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=10, pady=6)
        self.generate_button = ttk.Button(
            frame, text="Generate", command=self._on_generate_clicked
        )
        self.generate_button.pack(side="left")
        self._cancel_button = ttk.Button(
            frame, text="Cancel", command=self._cancel_work
        )
        self._cancel_button.pack(side="left", padx=6)
        self._replay_button = ttk.Button(
            frame, text="Play / Replay", command=self._replay_preview
        )
        self._replay_button.pack(side="left")
        ttk.Button(frame, text="Stop", command=self._stop_playback).pack(
            side="left", padx=6
        )
        self.progress_bar = ttk.Progressbar(
            frame, mode="determinate", maximum=1, value=0
        )
        self.progress_bar.pack(side="left", fill="x", expand=True)
        ttk.Label(self, textvariable=self._status_var, wraplength=760).pack(
            fill="x", padx=10, pady=4
        )
        ttk.Label(self, textvariable=self._elapsed_var).pack(
            anchor="w", padx=10, pady=(0, 6)
        )

    def _text_modified(self, event: tk.Event) -> None:
        if self.text_box.edit_modified():
            text = self.text_box.get("1.0", "end-1c")
            self._count_var.set(f"{len(text.split())} words · {len(text)} characters")
            self.text_box.edit_modified(False)

    def _paste_text(self) -> None:
        try:
            self.text_box.insert("insert", self.clipboard_get())
        except tk.TclError:
            self._status_var.set("The clipboard does not contain text.")

    def _provider_changed(self) -> None:
        if self._provider_id == "edge":
            self._edge_processing = self._process_text_var.get()
        self._voice_selections[self._provider_id] = tuple(
            voice.get() for speaker, voice in self._speaker_rows
        )
        self._provider_id = self._choice_names[self._provider_var.get()]
        choice = self._choices[self._provider_id]
        self._process_text_var.set(self._edge_processing if choice.online else True)
        previous = self._voice_selections.get(self._provider_id)
        for index, (_speaker, voice) in enumerate(self._speaker_rows):
            if previous is not None:
                voice.set(previous[index])
            else:
                voice.set(choice.voices[index % len(choice.voices)].voice_id)
        languages = tuple(sorted({voice.language for voice in choice.voices}))
        self._language_box.configure(values=("All languages", *languages))
        self._language_var.set("All languages")
        self._filter_voices()
        if choice.online:
            self._provider_status.set(
                "Online · Edge sends the script to Microsoft's service. FFmpeg is required."
            )
        else:
            model = self._provider_manager.models.manifest(choice.model_id)
            self._provider_status.set(
                f"Offline CPU · {model.runtime}. Install/verify assets in Model library."
            )
        self._apply_control_states()
        self._invalidate_preview()

    def _filter_voices(self) -> None:
        choice = self._choices[self._provider_id]
        language = self._language_var.get()
        values = tuple(
            voice.voice_id
            for voice in choice.voices
            if language == "All languages" or voice.language == language
        )
        for box in self._voice_boxes:
            box.configure(values=values)

    def _apply_control_states(self) -> None:
        choice = self._choices[self._provider_id]
        state = "disabled" if self._busy or self._closing else "normal"
        self._provider_box.configure(
            state="disabled" if self._busy or self._closing else "readonly"
        )
        self._language_box.configure(
            state="disabled" if self._busy or self._closing else "readonly"
        )
        self._model_library_button.configure(state=state)
        for entry in self._speaker_entries:
            entry.configure(state=state)
        for box in self._voice_boxes:
            box.configure(
                state="disabled"
                if self._busy or self._closing
                else ("normal" if choice.online else "readonly")
            )
        for button in self._preview_buttons:
            button.configure(state=state)
        self._speed_control.configure(
            state=state if choice.supports_speed else "disabled"
        )
        self._process_control.configure(state=state if choice.online else "disabled")
        processing = self._process_text_var.get() or not choice.online
        for control in (self._sentence_control, self._paragraph_control):
            control.configure(state=state if processing else "disabled")
        self._replay_button.configure(
            state=state if self._last_preview is not None else "disabled"
        )
        export_state = "disabled" if self._busy or self._closing else "readonly"
        self._format_box.configure(state=export_state)
        self._sample_rate_box.configure(state=export_state)
        self._channels_box.configure(state=export_state)
        self._bitrate_box.configure(
            state=export_state if self._format_var.get() == "MP3" else "disabled"
        )
        self._normalize_control.configure(state=state)

    def _read_voice_options(self) -> DesktopGenerationOptions:
        return build_desktop_options(
            self._choices[self._provider_id],
            self._speed_var.get(),
            self._process_text_var.get(),
            self._sentence_pause_var.get(),
            self._paragraph_pause_var.get(),
        )

    def _read_options(self) -> DesktopGenerationOptions:
        options = self._read_voice_options()
        settings = build_export_settings(
            self._format_var.get().lower(),
            self._bitrate_var.get(),
            self._sample_rate_var.get(),
            self._channels_var.get(),
            self._normalize_var.get(),
        )
        return replace(options, export_settings=settings)

    def _open_model_library(self) -> None:
        self._invalidate_preview()
        if self._model_library is None or not self._model_library.winfo_exists():
            self._model_library = ModelLibraryWindow(
                self, self._provider_manager.models, self._provider_manager.close
            )
        else:
            self._model_library.lift()

    def _choose_output_path(self) -> None:
        chosen = filedialog.asksaveasfilename(
            title="Choose output audio file",
            defaultextension=f".{self._format_var.get().lower()}",
            filetypes=[
                ("MP3 audio", "*.mp3"),
                ("WAV audio", "*.wav"),
                ("M4A audio", "*.m4a"),
            ],
            initialfile=Path(self._output_path_var.get()).name,
        )
        if chosen:
            self._output_path_var.set(chosen)
            suffix = Path(chosen).suffix.lower()
            if suffix in {".mp3", ".wav", ".m4a"}:
                self._format_var.set(suffix[1:].upper())
                self._apply_control_states()

    def _open_output_folder(self) -> None:
        directory = Path(
            self._output_path_var.get().strip() or str(default_desktop_output_path())
        ).parent
        try:
            directory.mkdir(parents=True, exist_ok=True)
            os.startfile(directory)
        except OSError as error:
            messagebox.showerror(APP_TITLE, str(error))

    def _begin_work(self, operation: str) -> None:
        self._player.stop()
        self._cancellation_token = CancellationToken()
        self._operation_kind = operation
        self._chunk_progress_active = False
        self._exporting = False
        self._started_at = time.monotonic()
        self._set_busy(True)
        self._status_var.set(
            "Generating..."
            if operation == "generation"
            else "Generating voice preview..."
        )
        self.progress_bar.configure(value=0, maximum=1)

    def _on_generate_clicked(self) -> None:
        if self._closing or (self._worker is not None and self._worker.is_alive()):
            return
        script_text = self.text_box.get("1.0", "end")
        try:
            validate_script_text(script_text)
            voices = build_speaker_voice_mapping(
                [(speaker.get(), voice.get()) for speaker, voice in self._speaker_rows]
            )
            options = self._read_options()
        except ValueError as error:
            messagebox.showerror(APP_TITLE, str(error))
            return
        final_audio = Path(
            self._output_path_var.get().strip() or str(default_desktop_output_path())
        )
        if options.export_settings is not None:
            if final_audio.exists():
                if not messagebox.askyesno(
                    APP_TITLE, "Replace the existing output audio file?"
                ):
                    return
                options = replace(
                    options,
                    export_settings=replace(options.export_settings, overwrite=True),
                )
            try:
                validate_export_target(final_audio, options.export_settings)
            except (OSError, ValueError) as error:
                messagebox.showerror(APP_TITLE, str(error))
                return
        output_dir = final_audio.parent / DEFAULT_OUTPUT_DIR.name
        self._begin_work("generation")
        self._worker = threading.Thread(
            target=self._run_generation,
            args=(
                script_text,
                output_dir,
                final_audio,
                voices,
                options,
                self._cancellation_token,
            ),
            daemon=True,
        )
        self._worker.start()

    def _on_preview_clicked(self, slot: int) -> None:
        if self._closing or (self._worker is not None and self._worker.is_alive()):
            return
        try:
            options = self._read_voice_options()
            voice_id = self._speaker_rows[slot][1].get().strip()
            try:
                selected_text = self.text_box.get("sel.first", "sel.last")
            except tk.TclError:
                selected_text = None
            if selected_text:
                speakers = {
                    speaker.get().strip() for speaker, voice in self._speaker_rows
                }
                selected_text = strip_speaker_labels(selected_text, speakers)
        except ValueError as error:
            messagebox.showerror(APP_TITLE, str(error))
            return
        self._begin_work("preview")
        self._worker = threading.Thread(
            target=self._run_preview,
            args=(
                options,
                voice_id,
                selected_text,
                self._cancellation_token,
                self._preview_revision,
            ),
            daemon=True,
        )
        self._worker.start()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.generate_button.configure(
            state="disabled" if busy or self._closing else "normal"
        )
        self._cancel_button.configure(
            state="normal" if busy and not self._closing else "disabled"
        )
        self._apply_control_states()

    def _cancel_work(self) -> None:
        self._cancellation_token.cancel()
        self._status_var.set("Cancellation requested; waiting for cleanup...")

    def _invalidate_preview(self) -> None:
        self._preview_revision += 1
        self._last_preview = None
        self._player.stop()
        if self._operation_kind == "preview" and self._busy:
            self._cancellation_token.cancel()
        self._replay_button.configure(state="disabled")

    def _stop_playback(self) -> None:
        self._player.stop()

    def _replay_preview(self) -> None:
        if self._last_preview is not None:
            try:
                self._player.play(self._last_preview)
            except (OSError, RuntimeError) as error:
                messagebox.showerror(APP_TITLE, f"Could not play the preview: {error}")

    def _run_generation(
        self,
        script_text: str,
        output_dir: Path,
        final_audio: Path,
        voices: dict[str, str],
        options: DesktopGenerationOptions,
        token: CancellationToken,
    ) -> None:
        def on_progress(index: int, total: int, line: ConversationLine) -> None:
            self._queue.put(
                _ProgressMessage(
                    "progress", index=index, total=total, speaker=line.speaker
                )
            )

        def on_chunk_progress(index: int, total: int, chunk: SpeechChunk) -> None:
            self._queue.put(
                _ProgressMessage(
                    "chunk_progress", index=index, total=total, speaker=chunk.speaker
                )
            )

        def on_export_progress(stage: str) -> None:
            self._queue.put(_ProgressMessage("export_progress", message=stage))

        try:
            provider = self._provider_manager.get(options.provider_id)
            result = asyncio.run(
                generate_conversation(
                    input_text=script_text,
                    output_dir=output_dir,
                    final_audio=final_audio,
                    voices=voices,
                    on_progress=on_progress,
                    on_chunk_progress=on_chunk_progress,
                    provider_id=options.provider_id,
                    provider=provider,
                    cancellation_token=token,
                    speed=options.speed,
                    text_settings=options.text_settings,
                    export_settings=options.export_settings,
                    on_export_progress=on_export_progress,
                )
            )
            self._queue.put(_ProgressMessage("success", final_audio=result))
        except asyncio.CancelledError:
            self._queue.put(_ProgressMessage("cancelled"))
        except Exception as error:
            self._queue.put(
                _ProgressMessage("error", message=format_generation_error(error))
            )

    def _run_preview(
        self,
        options: DesktopGenerationOptions,
        voice_id: str,
        selected_text: str | None,
        token: CancellationToken,
        revision: int,
    ) -> None:
        try:
            output = asyncio.run(
                self._preview_service.generate(
                    options.provider_id, voice_id, selected_text, options.speed, token
                )
            )
            self._queue.put(
                _ProgressMessage("preview_ready", path=output, revision=revision)
            )
        except asyncio.CancelledError:
            self._queue.put(_ProgressMessage("cancelled"))
        except Exception as error:
            self._queue.put(
                _ProgressMessage("error", message=format_generation_error(error))
            )

    def _drain_queue(self) -> None:
        try:
            while True:
                self._handle_message(self._queue.get_nowait())
        except queue.Empty:
            pass
        if self._busy and not self._closing:
            self._elapsed_var.set(
                f"Elapsed: {time.monotonic() - self._started_at:.1f} s"
            )
        if self._closing and (self._worker is None or not self._worker.is_alive()):
            if not self._shutdown_started:
                self._shutdown_started = True
                self._worker = threading.Thread(
                    target=self._provider_manager.close, daemon=True
                )
                self._worker.start()
            else:
                self.destroy()
                return
        self.after(self.POLL_INTERVAL_MS, self._drain_queue)

    def _handle_message(self, message: _ProgressMessage) -> None:
        if message.kind == "export_progress":
            if not self._exporting:
                self.progress_bar.configure(mode="indeterminate")
                self.progress_bar.start(10)
                self._exporting = True
            self._status_var.set(message.message)
            return
        if message.kind in {"progress", "chunk_progress"}:
            if message.kind == "chunk_progress":
                self._chunk_progress_active = True
            if message.kind == "chunk_progress" or not self._chunk_progress_active:
                self.progress_bar.configure(value=message.index, maximum=message.total)
            self._status_var.set(
                f"Generating {message.speaker}: {message.index}/{message.total}..."
            )
            return
        if self._exporting:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self._exporting = False
        self._set_busy(False)
        if self._closing:
            return
        if message.kind == "success":
            final_audio = message.final_audio
            self._status_var.set(f"Done. Saved to: {final_audio}")
            messagebox.showinfo(APP_TITLE, f"Final audio created:\n{final_audio}")
        elif message.kind == "preview_ready":
            if (
                message.revision != self._preview_revision
                or self._cancellation_token.is_cancelled
            ):
                self._status_var.set(
                    "Preview settings changed; generate a new preview."
                )
                return
            self._last_preview = message.path
            self._replay_button.configure(state="normal")
            self._status_var.set("Preview ready. Play/replay or stop at any time.")
            self._replay_preview()
        elif message.kind == "cancelled":
            self._status_var.set("Cancelled. Existing final audio is preserved.")
        elif message.kind == "error":
            self._status_var.set("Operation failed. See the error message.")
            messagebox.showerror(APP_TITLE, message.message)

    def _on_close(self) -> None:
        self._closing = True
        self._set_busy(True)
        self._cancellation_token.cancel()
        self._player.stop()
        self._status_var.set("Waiting for cleanup before closing...")


def main() -> None:
    app = TTSDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
