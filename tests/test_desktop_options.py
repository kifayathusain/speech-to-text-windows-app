"""Desktop option parsing honors provider capabilities and original Edge defaults."""

import pytest

from ttsapp.desktop_options import build_desktop_options
from ttsapp.provider_manager import ProviderChoice


def test_edge_ignores_disabled_controls_and_preserves_legacy_processing() -> None:
    choice = ProviderChoice("edge", "Edge", (), True, False)
    options = build_desktop_options(choice, "unused", False, "unused", "unused")
    assert options.speed is None
    assert options.text_settings is None


def test_offline_controls_create_explicit_speed_and_processing_settings() -> None:
    choice = ProviderChoice("kokoro", "Kokoro", (), False, True)
    options = build_desktop_options(choice, "0.8", False, "0.15", "0.4")
    assert options.speed == 0.8
    assert options.text_settings.sentence_pause_seconds == 0.15
    assert options.text_settings.paragraph_pause_seconds == 0.4


@pytest.mark.parametrize("speed", ["fast", "nan", "0", "3"])
def test_invalid_speed_is_rejected_before_starting_worker(speed: str) -> None:
    choice = ProviderChoice("kokoro", "Kokoro", (), False, True)
    with pytest.raises(ValueError, match="speed"):
        build_desktop_options(choice, speed, True, "0", "0.35")
