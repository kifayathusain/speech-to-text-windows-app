"""Opt-in real desktop export configuration, progress, and overwrite choices."""

import os
import time
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse

import pytest

from ttsapp import gui
from ttsapp.audio_export import probe_audio
from ttsapp.gui import TTSDesktopApp
from ttsapp.models.manager import ModelManager
from ttsapp.provider_manager import ProviderManager
from ttsapp.providers.base import CancellationToken


@pytest.mark.integration
@pytest.mark.real_model
@pytest.mark.skipif(
    not os.environ.get("TTS_GUI_PIPER_MODEL_DIR")
    or os.environ.get("TTS_EXPORT_TESTS") != "1",
    reason="Enable real Piper desktop and FFmpeg/FFprobe export testing.",
)
def test_real_desktop_m4a_wav_export_and_explicit_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assets = Path(os.environ["TTS_GUI_PIPER_MODEL_DIR"])

    def open_asset(url: str) -> BinaryIO:
        return (assets / Path(urlparse(url).path).name).open("rb")

    models = ModelManager(tmp_path / "models", opener=open_asset)
    models.install("piper-lessac-low")
    providers = ProviderManager(models)
    app = TTSDesktopApp(providers)
    app.withdraw()
    errors: list[str] = []
    completed: list[str] = []
    heartbeat: list[float] = []
    monkeypatch.setattr(
        gui.messagebox, "showerror", lambda title, text: errors.append(text)
    )
    monkeypatch.setattr(
        gui.messagebox, "showinfo", lambda title, text: completed.append(text)
    )
    app._provider_var.set("Piper")
    app._provider_changed()
    app.text_box.insert(
        "1.0", "Receptionist: This export uses the selected local voice."
    )
    app._output_path_var.set(str(tmp_path / "final.mp3"))
    app._format_var.set("M4A")
    app._export_format_changed()

    def wait_for_job() -> None:
        started = time.monotonic()

        def poll() -> None:
            heartbeat.append(time.monotonic())
            if not app._busy or time.monotonic() - started > 30:
                app.quit()
                return
            app.after(20, poll)

        app.after(20, poll)
        app.mainloop()
        assert not app._busy
        assert not errors

    try:
        app._on_generate_clicked()
        wait_for_job()
        m4a = tmp_path / "final.m4a"
        assert completed and probe_audio(m4a, CancellationToken()).codec == "aac"
        assert len(heartbeat) > 3
        previous_worker = app._worker
        monkeypatch.setattr(gui.messagebox, "askyesno", lambda *args: False)
        app._on_generate_clicked()
        assert app._worker is previous_worker
        app._format_var.set("WAV")
        app._export_format_changed()
        output_wave = tmp_path / "final.wav"
        output_wave.write_bytes(b"previous")
        monkeypatch.setattr(gui.messagebox, "askyesno", lambda *args: True)
        app._on_generate_clicked()
        wait_for_job()
        assert probe_audio(output_wave, CancellationToken()).codec == "pcm_s16le"
        app._on_close()
        app.mainloop()
        models.remove("piper-lessac-low")
    finally:
        if app._worker is not None:
            app._cancellation_token.cancel()
            app._worker.join(timeout=10)
        providers.close()
        with suppress(gui.tk.TclError):
            app.destroy()
