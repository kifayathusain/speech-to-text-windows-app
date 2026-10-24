"""Desktop startup provides recovery guidance for damaged packaged media."""

import sys
from tkinter import messagebox

import pytest

import app


def test_media_integrity_failure_has_actionable_desktop_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors = []

    def unavailable() -> None:
        raise ValueError("technical detail")

    monkeypatch.setattr(sys, "argv", ["WindowsTTSApp.exe"])
    monkeypatch.setattr(app, "configure_bundled_media", unavailable)
    monkeypatch.setattr(messagebox, "showerror", lambda *args: errors.append(args))
    assert app.main() == 1
    assert len(errors) == 1
    assert "Extract the complete original ZIP" in errors[0][1]
    assert "technical detail" not in errors[0][1]
