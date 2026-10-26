"""Tkinter model-library window; network and verification work stay in workers."""

import asyncio
import queue
import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import messagebox, ttk

from .models.manager import (
    DownloadProgress,
    InstallationState,
    ModelManager,
)
from .providers.base import CancellationToken


@dataclass(frozen=True)
class _LibraryEvent:
    kind: str
    message: str = ""
    progress: DownloadProgress | None = None
    statuses: dict[str, InstallationState] | None = None


class ModelLibraryWindow(tk.Toplevel):
    """Show model prerequisites/licenses and manage verified local installations."""

    def __init__(
        self,
        parent: tk.Misc,
        manager: ModelManager | None = None,
        before_modify: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title("Offline model library")
        self.geometry("760x520")
        self.transient(parent)
        self.grab_set()
        self._before_modify = before_modify
        self._manager = manager if manager is not None else ModelManager()
        self._events: queue.Queue[_LibraryEvent] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._token = CancellationToken()
        self._closing = False
        self._status = tk.StringVar(value="Checking installed models...")
        self._details = tk.StringVar(
            value="Select a model to view runtime and license details."
        )
        self._build_widgets()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._poll_id = self.after(100, self._poll)
        self._verify()

    def _build_widgets(self) -> None:
        search = ttk.Frame(self)
        search.pack(fill="x", padx=12, pady=(8, 0))
        ttk.Label(search, text="Search models:").pack(side="left")
        self._search = tk.StringVar()
        ttk.Entry(search, textvariable=self._search).pack(
            side="left", fill="x", expand=True
        )
        self._search.trace_add("write", lambda *args: self._filter_models())
        table = ttk.Frame(self)
        table.pack(fill="both", expand=True, padx=12, pady=12)
        self._tree = ttk.Treeview(
            table,
            columns=("name", "size", "status"),
            show="headings",
            height=6,
            selectmode="browse",
        )
        for name, title, width in (
            ("name", "Model", 290),
            ("size", "Download", 90),
            ("status", "Installation", 260),
        ):
            self._tree.heading(name, text=title)
            self._tree.column(name, width=width)
        for model in self._manager.list_models():
            self._tree.insert(
                "",
                "end",
                iid=model.model_id,
                values=(
                    model.display_name,
                    f"{model.size_bytes / 1024**2:.1f} MiB",
                    "Checking...",
                ),
            )
        scrollbar = ttk.Scrollbar(table, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._tree.pack(side="left", fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", lambda event: self._show_details())
        ttk.Label(
            self, textvariable=self._details, wraplength=720, justify="left"
        ).pack(fill="x", padx=12, pady=6)
        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=12, pady=8)
        self._install_button = ttk.Button(
            controls, text="Download / Reinstall", command=self._install
        )
        self._install_button.pack(side="left")
        self._cancel_button = ttk.Button(
            controls, text="Cancel", command=self._token.cancel
        )
        self._cancel_button.pack(side="left", padx=6)
        self._remove_button = ttk.Button(controls, text="Remove", command=self._remove)
        self._remove_button.pack(side="left")
        self._verify_button = ttk.Button(controls, text="Verify", command=self._verify)
        self._verify_button.pack(side="left", padx=6)
        ttk.Button(
            controls, text="License information", command=self._open_license
        ).pack(side="left")
        self._progress = ttk.Progressbar(self, mode="determinate", maximum=100)
        self._progress.pack(fill="x", padx=12, pady=6)
        ttk.Label(self, textvariable=self._status, wraplength=720).pack(
            fill="x", padx=12, pady=8
        )

    def _selected_id(self) -> str | None:
        selection = self._tree.selection()
        if selection:
            return selection[0]
        self._status.set("Select a model first.")
        return None

    def _show_details(self) -> None:
        model_id = self._selected_id()
        if model_id is None:
            return
        model = self._manager.manifest(model_id)
        self._details.set(
            f"Voices ({len(model.voices)}): {', '.join(model.voices[:4])}"
            f"{' … (all speakers in main voice selector)' if len(model.voices) > 4 else ''}\n"
            f"Languages: {', '.join(model.languages)}\n"
            f"Runtime: {model.runtime}\nLicense: {model.license_name}\n"
            f"Attribution: {model.attribution}"
        )

    def _filter_models(self) -> None:
        """Keep tree records/statuses while showing only matching model names."""
        query = self._search.get().casefold()
        for model in self._manager.list_models():
            if query in f"{model.model_id} {model.display_name}".casefold():
                self._tree.move(model.model_id, "", "end")
            else:
                self._tree.detach(model.model_id)

    def _open_license(self) -> None:
        model_id = self._selected_id()
        if model_id is not None:
            webbrowser.open(self._manager.manifest(model_id).license_url)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in (self._install_button, self._remove_button, self._verify_button):
            button.configure(state=state)
        self._cancel_button.configure(state="normal" if busy else "disabled")

    def _start_operation(self, operation: Callable[[], str]) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._token = CancellationToken()
        self._cancel_button.configure(command=self._token.cancel)
        self._set_busy(True)
        self._progress.configure(value=0)

        def work() -> None:
            try:
                message = operation()
                statuses = {
                    model.model_id: self._manager.status(model.model_id)
                    for model in self._manager.list_models()
                }
                self._events.put(_LibraryEvent("complete", message, statuses=statuses))
            except asyncio.CancelledError:
                self._events.put(
                    _LibraryEvent(
                        "cancelled", "Download cancelled; incomplete files removed."
                    )
                )
            except (OSError, ValueError, RuntimeError) as error:
                self._events.put(_LibraryEvent("error", str(error)))

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def _install(self) -> None:
        model_id = self._selected_id()
        if model_id is None:
            return
        self._status.set("Downloading and verifying model files...")

        def install() -> str:
            if self._before_modify is not None:
                self._before_modify()
            self._manager.install(
                model_id,
                self._token,
                lambda progress: self._events.put(
                    _LibraryEvent("progress", progress=progress)
                ),
            )
            return "Model installed and verified. Runtime dependencies are installed separately."

        self._start_operation(install)

    def _remove(self) -> None:
        model_id = self._selected_id()
        if model_id is None:
            return
        if not messagebox.askyesno(
            "Remove model", "Remove the selected local model files?", parent=self
        ):
            return

        def remove() -> str:
            if self._before_modify is not None:
                self._before_modify()
            self._manager.remove(model_id)
            return "Selected model removed."

        self._start_operation(remove)

    def _verify(self) -> None:
        self._start_operation(lambda: "Model integrity checked.")

    def _poll(self) -> None:
        try:
            while True:
                event = self._events.get_nowait()
                if event.progress is not None:
                    progress = event.progress
                    self._progress.configure(
                        value=100 * progress.downloaded_bytes / progress.total_bytes
                    )
                    self._status.set(f"Downloading {progress.filename}...")
                else:
                    self._set_busy(False)
                    self._status.set(event.message)
                    if event.statuses is not None:
                        for identifier, status in event.statuses.items():
                            self._tree.set(identifier, "status", status.value)
                    if event.kind == "error":
                        messagebox.showerror(
                            "Model library", event.message, parent=self
                        )
        except queue.Empty:
            pass
        if self._closing and (self._worker is None or not self._worker.is_alive()):
            self.destroy()
            return
        self._poll_id = self.after(100, self._poll)

    def _close(self) -> None:
        self._closing = True
        self._token.cancel()
        self._status.set("Waiting for the current operation to clean up...")

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget == self:
            self._token.cancel()
            self.after_cancel(self._poll_id)
