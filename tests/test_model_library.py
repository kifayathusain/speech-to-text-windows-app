"""Worker/UI separation for the model library without constructing Tk widgets."""

import queue
import threading
from pathlib import Path

from ttsapp.model_library import ModelLibraryWindow
from ttsapp.models.manager import ModelManager


def test_model_operation_does_not_touch_widgets_from_worker(tmp_path: Path) -> None:
    main_thread = threading.current_thread()
    widget_threads: list[threading.Thread] = []
    operation_threads: list[threading.Thread] = []

    class Widget:
        def configure(self, **kwargs: object) -> None:
            widget_threads.append(threading.current_thread())

    window = ModelLibraryWindow.__new__(ModelLibraryWindow)
    window._manager = ModelManager(tmp_path, ())
    window._events = queue.Queue()
    window._worker = None
    window._cancel_button = Widget()
    window._install_button = Widget()
    window._remove_button = Widget()
    window._verify_button = Widget()
    window._progress = Widget()

    def operation() -> str:
        operation_threads.append(threading.current_thread())
        return "Finished"

    window._start_operation(operation)
    window._worker.join(timeout=2)

    assert not window._worker.is_alive()
    assert operation_threads and operation_threads[0] is not main_thread
    assert widget_threads and all(thread is main_thread for thread in widget_threads)
    event = window._events.get_nowait()
    assert event.kind == "complete"
    assert event.message == "Finished"
