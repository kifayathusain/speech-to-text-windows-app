"""Opt-in Windows M11 selection, preview and mixed-model export acceptance."""

import os
import time
from contextlib import suppress
from pathlib import Path

import pytest

from ttsapp import gui
from ttsapp.audio_export import ExportSettings, export_audio, probe_audio
from ttsapp.gui import TTSDesktopApp
from ttsapp.models.manager import ModelManager
from ttsapp.preview import PreviewService
from ttsapp.provider_manager import ProviderManager
from ttsapp.providers.base import CancellationToken


@pytest.mark.integration
@pytest.mark.real_model
@pytest.mark.skipif(
    not os.environ.get("TTS_M11_MODEL_ROOT"),
    reason="Set TTS_M11_MODEL_ROOT with verified Lessac, Alan low and ARU models.",
)
def test_real_windows_search_multispeaker_preview_and_mixed_model_exports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = ModelManager(Path(os.environ["TTS_M11_MODEL_ROOT"]))
    providers = ProviderManager(manager)
    app = TTSDesktopApp(providers)
    app.withdraw()
    errors = []
    previews = []
    heartbeat = []

    class Player:
        def play(self, path: Path) -> None:
            previews.append(path)

        def stop(self) -> None:
            pass

    app._player = Player()
    app._preview_service = PreviewService(providers, tmp_path / "previews")
    monkeypatch.setattr(
        gui.messagebox, "showerror", lambda title, text: errors.append(text)
    )
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *args: None)

    def wait_for_job() -> None:
        started = time.monotonic()

        def poll() -> None:
            heartbeat.append(time.monotonic())
            if not app._busy or time.monotonic() - started > 60:
                app.quit()
            else:
                app.after(20, poll)

        app.after(20, poll)
        app.mainloop()
        assert not app._busy
        assert not errors

    try:
        app._provider_var.set("Piper")
        app._provider_changed()
        app._language_var.set("en-GB")
        app._voice_search_var.set("aru speaker_11")
        assert tuple(app._voice_boxes[0]["values"]) == ("en_GB-aru-medium:speaker_11",)
        app._speaker_rows[0][1].set("en_GB-aru-medium:speaker_11")
        assert "Files present" in app._voice_details[0].get()
        app._on_preview_clicked(0)
        wait_for_job()
        app._speaker_rows[0][1].set("en_GB-aru-medium:speaker_0")
        app._on_preview_clicked(0)
        wait_for_job()
        assert len(previews) == 2 and previews[0] != previews[1]
        assert all(path.is_file() for path in previews)

        app._voice_search_var.set("")
        app._speaker_rows[0][1].set("en_GB-alan-low")
        app._speaker_rows[1][1].set("en_US-lessac-low")
        first_name = app._speaker_rows[0][0].get()
        second_name = app._speaker_rows[1][0].get()
        app.text_box.insert(
            "1.0",
            f"{first_name}: Hello from Britain.\n{second_name}: Hello from America.",
        )
        source = tmp_path / "mixed.wav"
        app._format_var.set("WAV")
        app._output_path_var.set(str(source))
        app._on_generate_clicked()
        wait_for_job()
        token = CancellationToken()
        assert probe_audio(source, token).codec == "pcm_s16le"
        for container, codec in (("mp3", "mp3"), ("m4a", "aac")):
            output = tmp_path / f"mixed.{container}"
            export_audio([source], output, ExportSettings(container), token)
            assert probe_audio(output, token).codec == codec
        assert len(heartbeat) > 5

        app._open_model_library()
        library = app._model_library
        library._search.set("alan")
        assert len(library._tree.get_children()) == 2
        library._tree.selection_set("piper-en_gb-alan-low")
        library._show_details()
        assert "License:" in library._details.get()
        library._close()
        deadline = time.monotonic() + 30
        while library.winfo_exists() and time.monotonic() < deadline:
            app.update()
            time.sleep(0.01)
        assert not library.winfo_exists()
    finally:
        if app._worker is not None:
            app._cancellation_token.cancel()
            app._worker.join(timeout=10)
        providers.close()
        with suppress(gui.tk.TclError):
            app.destroy()
