"""Pinned unquantized Kokoro-82M v1.0 model and initial English voice choices."""

from pathlib import Path

from ..providers.base import VoiceMetadata
from ..providers.kokoro import KokoroModel
from .assets import assets_from_manifest
from .catalog import default_manifest


def kokoro_v1_model(model_directory: Path) -> KokoroModel:
    """Describe verified upstream assets without downloading or opening them."""
    assets = assets_from_manifest(default_manifest("kokoro-82m-v1"), model_directory)
    voices = tuple(
        VoiceMetadata(identifier, name, language, "kokoro-82m-v1.0", "Apache-2.0")
        for identifier, name, language in (
            ("af_heart", "Heart (US English)", "en-US"),
            ("af_bella", "Bella (US English)", "en-US"),
            ("am_adam", "Adam (US English)", "en-US"),
            ("bf_emma", "Emma (British English)", "en-GB"),
        )
    )
    return KokoroModel(
        assets["kokoro-v1.0.onnx"],
        assets["voices-v1.0.bin"],
        voices,
    )
