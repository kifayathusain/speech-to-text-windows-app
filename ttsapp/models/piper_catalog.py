"""Pinned Piper voice descriptor; installation and downloads remain explicit."""

from pathlib import Path

from ..providers.base import VoiceMetadata
from ..providers.piper import PiperModel
from .assets import assets_from_manifest
from .catalog import default_manifest


def lessac_low_model(model_directory: Path) -> PiperModel:
    """Describe upstream Lessac low assets without downloading or loading them."""
    assets = assets_from_manifest(default_manifest("piper-lessac-low"), model_directory)
    return PiperModel(
        voice=VoiceMetadata(
            voice_id="en_US-lessac-low",
            display_name="Lessac (US English, low)",
            language="en-US",
            model_id="piper-en_US-lessac-low",
            license_name="Upstream Lessac dataset license; see setup documentation",
        ),
        model=assets["en_US-lessac-low.onnx"],
        configuration=assets["en_US-lessac-low.onnx.json"],
    )
