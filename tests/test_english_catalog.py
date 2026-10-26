"""Complete pinned English inventories and discoverability without model files."""

import json
from pathlib import Path

import pytest

from ttsapp.desktop_options import filter_voice_choices
from ttsapp.models.catalog import default_catalog, default_manifest
from ttsapp.models.english_catalog import piper_english_catalog
from ttsapp.models.kokoro_catalog import kokoro_v1_model
from ttsapp.models.manager import ModelManager
from ttsapp.models.piper_catalog import english_models
from ttsapp.provider_manager import ProviderManager


def test_kokoro_catalog_has_exact_official_english_inventory(tmp_path: Path) -> None:
    expected = {
        "af_heart",
        "af_alloy",
        "af_aoede",
        "af_bella",
        "af_jessica",
        "af_kore",
        "af_nicole",
        "af_nova",
        "af_river",
        "af_sarah",
        "af_sky",
        "am_adam",
        "am_echo",
        "am_eric",
        "am_fenrir",
        "am_liam",
        "am_michael",
        "am_onyx",
        "am_puck",
        "am_santa",
        "bf_alice",
        "bf_emma",
        "bf_isabella",
        "bf_lily",
        "bm_daniel",
        "bm_fable",
        "bm_george",
        "bm_lewis",
    }
    model = kokoro_v1_model(tmp_path)
    assert {voice.voice_id for voice in model.voices} == expected
    assert set(default_manifest("kokoro-82m-v1").voices) == expected
    assert sum(voice.language == "en-US" for voice in model.voices) == 20
    assert sum(voice.language == "en-GB" for voice in model.voices) == 8


def test_piper_inventory_preserves_variants_speakers_and_integrity(
    tmp_path: Path,
) -> None:
    catalog = piper_english_catalog()
    assert len(catalog) == 38
    assert sum(len(entry.speakers) for entry in catalog) == 2006
    assert sum(entry.manifest.languages == ("en-GB",) for entry in catalog) == 11
    assert sum(entry.manifest.languages == ("en-US",) for entry in catalog) == 27
    identifiers = []
    for entry in catalog:
        manifest = default_manifest(entry.manifest.model_id)
        models = english_models(tmp_path / manifest.model_id, manifest.model_id)
        assert tuple(model.voice.voice_id for model in models) == manifest.voices
        assert len(manifest.files) == 3
        assert all(len(asset.sha256) == 64 for asset in manifest.files)
        assert all(
            "5041a7a49ae5b3a0f30e6837769eb03fdbb231bd" in asset.url
            for asset in manifest.files
        )
        if len(models) > 1:
            assert {model.speaker_id for model in models} == set(range(len(models)))
        identifiers.extend(manifest.voices)
    assert len(set(identifiers)) == 2006
    assert len(default_catalog()) == 39


def test_libritts_r_uses_verified_config_instead_of_incorrect_index_count() -> None:
    snapshot = json.loads(Path("ttsapp/models/piper_english.json").read_text("utf-8"))
    entry = next(
        model
        for model in snapshot["models"]
        if model["key"] == "en_US-libritts_r-medium"
    )
    assert entry["index_num_speakers"] == 2306
    assert entry["num_speakers"] == len(entry["speakers"]) == 904


def test_lessac_installation_identity_and_hashes_are_preserved() -> None:
    model = default_manifest("piper-lessac-low")
    assert model.version == "1.0.0"
    assert model.voices == ("en_US-lessac-low",)
    assert model.files[0].sha256 == (
        "f7d01dde371555732c4c314111ac79672b1a5ce2fc19266ab42178fd8df7f375"
    )


@pytest.mark.parametrize(
    ("language", "query", "count"),
    [
        ("en-GB", "alan medium", 1),
        ("en-US", "libritts_r speaker_903", 1),
        ("en-GB", "libritts", 0),
        ("All languages", "nonexistent", 0),
    ],
)
def test_search_filters_locale_quality_and_speaker(
    tmp_path: Path, language: str, query: str, count: int
) -> None:
    manager = ProviderManager(ModelManager(tmp_path / "absent"))
    choice = next(
        choice for choice in manager.list_choices() if choice.provider_id == "piper"
    )
    assert len(filter_voice_choices(choice, language, query)) == count
    assert not (tmp_path / "absent").exists()
