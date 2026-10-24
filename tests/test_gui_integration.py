"""Opt-in real Tkinter event-loop and native audio playback acceptance checks."""

import asyncio
import os
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse

import pytest

from ttsapp import gui
from ttsapp.audio_files import write_silence
from ttsapp.gui import TTSDesktopApp
from ttsapp.models.manager import ModelManager
from ttsapp.preview import PreviewService, WindowsAudioPlayer
from ttsapp.provider_manager import ProviderManager
from ttsapp.providers.base import CancellationToken


@pytest.mark.integration
@pytest.mark.real_model
@pytest.mark.skipif(
    not os.environ.get("TTS_GUI_PIPER_MODEL_DIR"),
    reason="Set TTS_GUI_PIPER_MODEL_DIR with a real Windows Tkinter display/runtime.",
)
def test_real_piper_preview_keeps_tkinter_responsive_and_invalidates_settings(
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
    main_thread = threading.current_thread()
    played_on: list[threading.Thread] = []
    heartbeat: list[float] = []
    errors: list[str] = []

    class Player:
        def play(self, path: Path) -> None:
            assert path.is_file()
            played_on.append(threading.current_thread())

        def stop(self) -> None:
            pass

    app._player = Player()
    app._preview_service = PreviewService(providers, tmp_path / "cache")
    monkeypatch.setattr(
        gui.messagebox, "showerror", lambda title, text: errors.append(text)
    )
    app._provider_var.set("Piper")
    app._provider_changed()
    app._on_preview_clicked(0)
    started = time.monotonic()

    def poll() -> None:
        heartbeat.append(time.monotonic())
        if not app._busy or time.monotonic() - started > 25:
            app.quit()
            return
        app.after(20, poll)

    app.after(20, poll)
    try:
        app.mainloop()
        assert not errors
        assert not app._busy
        assert app._last_preview is not None
        assert len(heartbeat) >= 3
        assert played_on == [main_thread]
        completed_preview = app._last_preview
        app._replay_preview()
        assert played_on == [main_thread, main_thread]
        app._speed_var.set("1.2")
        assert app._last_preview is None
        assert str(app._replay_button.cget("state")) == "disabled"

        class CancellablePreview:
            async def generate(
                self,
                provider_id: str,
                voice_id: str,
                selected_text: str | None,
                speed: float | None,
                token: CancellationToken,
            ) -> Path:
                await token.wait()
                raise asyncio.CancelledError

        app._preview_service = CancellablePreview()
        app._on_preview_clicked(0)
        app.after(120, app._cancel_work)
        app.after(20, poll)
        app.mainloop()
        assert not app._busy
        assert app._status_var.get().startswith("Cancelled")
        assert played_on == [main_thread, main_thread]
        app._cancellation_token = CancellationToken()
        app._handle_message(
            gui._ProgressMessage(
                "preview_ready",
                path=completed_preview,
                revision=app._preview_revision - 1,
            )
        )
        assert app._last_preview is None
        assert played_on == [main_thread, main_thread]
        app._on_close()
        app.mainloop()
        assert app._shutdown_started
        models.remove("piper-lessac-low")
    finally:
        if app._worker is not None:
            app._cancellation_token.cancel()
            app._worker.join(timeout=10)
        providers.close()
        with suppress(gui.tk.TclError):
            app.destroy()


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("TTS_PLAYBACK_TESTS") != "1",
    reason="Opt in to Windows playback API testing.",
)
def test_windows_native_playback_accepts_pcm_and_stops(tmp_path: Path) -> None:
    silence = tmp_path / "silence.wav"
    write_silence(silence, 16000, 0.1, CancellationToken())
    player = WindowsAudioPlayer()
    try:
        player.play(silence)
    finally:
        player.stop()
