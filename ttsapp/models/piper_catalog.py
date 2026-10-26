"""Pinned Piper voice descriptor; installation and downloads remain explicit."""

from pathlib import Path

from ..providers.base import VoiceMetadata
from ..providers.piper import PiperModel
from .assets import assets_from_manifest
from .catalog import default_manifest
from .english_catalog import piper_english_catalog


def english_models(model_directory: Path, model_id: str) -> tuple[PiperModel, ...]:
    """Describe every speaker in one pinned English model without loading it."""
    entry = next(
        (
            entry
            for entry in piper_english_catalog()
            if entry.manifest.model_id == model_id
        ),
        None,
    )
    if entry is None:
        raise ValueError(f"Unknown English Piper model: '{model_id}'.")
    manifest = default_manifest(model_id)
    assets = assets_from_manifest(manifest, model_directory)
    return tuple(
        PiperModel(
            voice=VoiceMetadata(
                speaker.voice_id,
                f"{entry.key} — {speaker.name}",
                manifest.languages[0],
                model_id,
                manifest.license_name,
            ),
            model=assets[f"{entry.key}.onnx"],
            configuration=assets[f"{entry.key}.onnx.json"],
            speaker_id=speaker.speaker_id,
        )
        for speaker in entry.speakers
    )


def lessac_low_model(model_directory: Path) -> PiperModel:
    """Describe upstream Lessac low assets without downloading or loading them."""
    return english_models(model_directory, "piper-lessac-low")[0]
