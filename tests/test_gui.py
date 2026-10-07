"""Tests for the non-Tkinter logic in the desktop UI module.

These test the plain functions ``validate_script_text`` and
``build_voice_overrides`` directly, without constructing any Tkinter
widgets, so they run headless in CI without a display.
"""

import pytest

from ttsapp.gui import build_voice_overrides, validate_script_text


def test_validate_script_text_rejects_empty_string():
    with pytest.raises(ValueError):
        validate_script_text("")


def test_validate_script_text_rejects_whitespace_only():
    with pytest.raises(ValueError):
        validate_script_text("   \n\n  ")


def test_validate_script_text_accepts_real_content():
    # Should not raise.
    validate_script_text("Receptionist: Hello there.\n")


def test_build_voice_overrides_keeps_defaults_when_blank():
    base = {"Receptionist": "en-GB-SoniaNeural", "Caller": "en-GB-RyanNeural"}

    merged = build_voice_overrides(base, {"Receptionist": "", "Caller": "  "})

    assert merged == base
    # Ensure the original dict was not mutated.
    assert base == {"Receptionist": "en-GB-SoniaNeural", "Caller": "en-GB-RyanNeural"}


def test_build_voice_overrides_applies_non_blank_overrides():
    base = {"Receptionist": "en-GB-SoniaNeural", "Caller": "en-GB-RyanNeural"}

    merged = build_voice_overrides(base, {"Receptionist": "en-US-JennyNeural"})

    assert merged == {
        "Receptionist": "en-US-JennyNeural",
        "Caller": "en-GB-RyanNeural",
    }
