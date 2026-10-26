"""Pinned English voice inventory shared by installers and provider factories."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .catalog import DownloadFile, ModelManifest

KOKORO_VOICE_IDS = (
    "af_heart",
    "af_bella",
    "am_adam",
    "bf_emma",
    "af_alloy",
    "af_aoede",
    "af_jessica",
    "af_kore",
    "af_nicole",
    "af_nova",
    "af_river",
    "af_sarah",
    "af_sky",
    "am_echo",
    "am_eric",
    "am_fenrir",
    "am_liam",
    "am_michael",
    "am_onyx",
    "am_puck",
    "am_santa",
    "bf_alice",
    "bf_isabella",
    "bf_lily",
    "bm_daniel",
    "bm_fable",
    "bm_george",
    "bm_lewis",
)


@dataclass(frozen=True)
class PiperSpeaker:
    """Stable application identity and upstream numeric synthesis speaker."""

    voice_id: str
    name: str
    speaker_id: int | None


@dataclass(frozen=True)
class PiperCatalogEntry:
    """One downloadable Piper model and all speakers in its verified config."""

    key: str
    manifest: ModelManifest
    speakers: tuple[PiperSpeaker, ...]


@lru_cache(maxsize=1)
def piper_english_catalog() -> tuple[PiperCatalogEntry, ...]:
    """Read bundled metadata only; never access the network or inference runtime."""
    snapshot = json.loads(
        Path(__file__).with_name("piper_english.json").read_text("utf-8")
    )
    entries = []
    for model in snapshot["models"]:
        key = model["key"]
        model_id = "piper-" + key.lower()
        if key == "en_US-lessac-low":
            model_id = "piper-lessac-low"
        if model["num_speakers"] == 1:
            speakers = (PiperSpeaker(key, key, None),)
        else:
            speakers = tuple(
                PiperSpeaker(f"{key}:speaker_{identifier}", name, identifier)
                for name, identifier in sorted(
                    model["speakers"].items(), key=lambda item: item[1]
                )
            )
        license_lines = [
            line.strip().removeprefix("* ")
            for line in model["model_card"].splitlines()
            if "license:" in line.lower()
        ]
        license_name = "; ".join(license_lines) or "See upstream MODEL_CARD"
        files = tuple(DownloadFile(**asset) for asset in model["files"])
        card_url = next(file.url for file in files if file.filename == "MODEL_CARD")
        manifest = ModelManifest(
            model_id=model_id,
            version=snapshot["revision"],
            provider_id="piper",
            display_name=f"Piper {key} ({len(speakers)} speaker(s))",
            files=files,
            voices=tuple(speaker.voice_id for speaker in speakers),
            languages=(model["language"],),
            license_name=f"{license_name}; runtime GPL-3.0-or-later",
            license_url=card_url,
            attribution=f"rhasspy/piper-voices; {key}. See installed MODEL_CARD.",
            runtime="requirements-piper.txt; CPU only",
        )
        entries.append(PiperCatalogEntry(key, manifest, speakers))
    return tuple(entries)
