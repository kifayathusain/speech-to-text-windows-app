"""Model transaction safety using tiny local downloads rather than real weights."""

import asyncio
import hashlib
import io
import os
from dataclasses import replace
from pathlib import Path
from urllib.error import URLError

import pytest

from ttsapp.models import manager as manager_module
from ttsapp.models.assets import ModelValidationError
from ttsapp.models.catalog import DownloadFile, ModelManifest
from ttsapp.models.manager import DownloadProgress, InstallationState, ModelManager
from ttsapp.providers.base import CancellationToken


@pytest.fixture
def model_manifest() -> ModelManifest:
    return ModelManifest(
        model_id="test-model",
        version="1",
        provider_id="piper",
        display_name="Test",
        files=(
            DownloadFile(
                "model.onnx",
                "https://github.com/test/model.onnx",
                7,
                hashlib.sha256(b"weights").hexdigest(),
            ),
            DownloadFile(
                "voice.json",
                "https://github.com/test/voice.json",
                2,
                hashlib.sha256(b"{}").hexdigest(),
            ),
        ),
        voices=("voice",),
        languages=("en-US",),
        license_name="Test license",
        license_url="https://github.com/test/LICENSE",
        attribution="Test fixtures",
        runtime="Controlled test runtime",
    )


def fixture_opener(url: str) -> io.BytesIO:
    """Return deterministic bytes; no test downloads model data."""
    if url.endswith(".onnx"):
        return io.BytesIO(b"weights")
    return io.BytesIO(b"{}")


def test_install_verify_corruption_reinstall_and_remove(
    tmp_path: Path, model_manifest: ModelManifest
) -> None:
    manager = ModelManager(tmp_path, (model_manifest,), fixture_opener)
    progress: list[DownloadProgress] = []
    assert manager.status("test-model") == InstallationState.NOT_INSTALLED

    installed = manager.install("test-model", on_progress=progress.append)

    assert manager.status("test-model") == InstallationState.INSTALLED
    assert progress[-1].downloaded_bytes == progress[-1].total_bytes == 9
    (installed / "model.onnx").write_bytes(b"changed")
    assert manager.status("test-model") == InstallationState.CORRUPT
    manager.install("test-model")
    assert manager.status("test-model") == InstallationState.INSTALLED
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    manager.remove("test-model")
    assert manager.status("test-model") == InstallationState.NOT_INSTALLED
    assert unrelated.is_dir()
    assert not list(tmp_path.glob(".staging-*"))
    assert not list(tmp_path.glob(".backup-*"))


@pytest.mark.parametrize("download", [b"short", b"too much data", b"corrupt"])
def test_invalid_download_keeps_previous_installation(
    tmp_path: Path, model_manifest: ModelManifest, download: bytes
) -> None:
    manager = ModelManager(tmp_path, (model_manifest,), fixture_opener)
    manager.install("test-model")
    failing = ModelManager(
        tmp_path, (model_manifest,), lambda url: io.BytesIO(download)
    )

    with pytest.raises(ModelValidationError):
        failing.install("test-model")

    assert manager.status("test-model") == InstallationState.INSTALLED
    assert not list(tmp_path.glob(".staging-*"))


def test_cancel_download_cleans_staging_without_activating_model(
    tmp_path: Path, model_manifest: ModelManifest
) -> None:
    token = CancellationToken()
    manager = ModelManager(tmp_path, (model_manifest,), fixture_opener)

    with pytest.raises(asyncio.CancelledError):
        manager.install("test-model", token, lambda progress: token.cancel())

    assert manager.status("test-model") == InstallationState.NOT_INSTALLED
    assert not list(tmp_path.glob(".staging-*"))
    manager.install("test-model")
    assert manager.status("test-model") == InstallationState.INSTALLED


def test_precancelled_install_does_not_create_storage(
    tmp_path: Path, model_manifest: ModelManifest
) -> None:
    token = CancellationToken()
    token.cancel()
    manager = ModelManager(tmp_path / "models", (model_manifest,), fixture_opener)

    with pytest.raises(asyncio.CancelledError):
        manager.install("test-model", token)

    assert list(tmp_path.iterdir()) == []


def test_activation_failure_restores_previous_verified_model(
    tmp_path: Path, model_manifest: ModelManifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = ModelManager(tmp_path, (model_manifest,), fixture_opener)
    manager.install("test-model")
    original_replace = os.replace

    def fail_activation(source: Path, destination: Path) -> None:
        if source.name.startswith(".staging-"):
            raise PermissionError("Cannot activate")
        original_replace(source, destination)

    monkeypatch.setattr(manager_module.os, "replace", fail_activation)
    with pytest.raises(PermissionError, match="Cannot activate"):
        manager.install("test-model")

    assert manager.status("test-model") == InstallationState.INSTALLED
    assert not list(tmp_path.glob(".staging-*"))
    assert not list(tmp_path.glob(".backup-*"))


def test_interrupted_activation_recovers_backup_even_if_new_download_fails(
    tmp_path: Path, model_manifest: ModelManifest
) -> None:
    manager = ModelManager(tmp_path, (model_manifest,), fixture_opener)
    installed = manager.install("test-model")
    backup = tmp_path / (".backup-test-model-" + "a" * 32)
    installed.rename(backup)
    staging = tmp_path / (".staging-test-model-" + "b" * 32)
    staging.mkdir()
    (staging / "partial").write_bytes(b"partial")

    def disconnected(url: str) -> io.BytesIO:
        raise URLError("connection lost")

    failing = ModelManager(tmp_path, (model_manifest,), disconnected)
    with pytest.raises(URLError, match="connection lost"):
        failing.install("test-model")

    assert manager.status("test-model") == InstallationState.INSTALLED
    assert not backup.exists()
    assert not staging.exists()


def test_invalid_backup_does_not_prevent_fresh_installation(
    tmp_path: Path, model_manifest: ModelManifest
) -> None:
    backup = tmp_path / (".backup-test-model-" + "c" * 32)
    backup.mkdir()
    manager = ModelManager(tmp_path, (model_manifest,), fixture_opener)

    manager.install("test-model")

    assert manager.status("test-model") == InstallationState.INSTALLED
    assert not backup.exists()


def test_model_lock_prevents_another_manager_from_removing_model(
    tmp_path: Path, model_manifest: ModelManifest
) -> None:
    manager = ModelManager(tmp_path, (model_manifest,), fixture_opener)
    manager.install("test-model")
    other = ModelManager(tmp_path, (model_manifest,), fixture_opener)

    with manager._operation_lock("test-model"), pytest.raises(OSError):
        other.remove("test-model")

    assert manager.status("test-model") == InstallationState.INSTALLED
    other.remove("test-model")
    assert manager.status("test-model") == InstallationState.NOT_INSTALLED


@pytest.mark.parametrize(
    "filename", ["../escape", "/absolute", "C:drive", "nested/file", ".."]
)
def test_catalog_rejects_unsafe_asset_names(filename: str) -> None:
    with pytest.raises(ValueError):
        DownloadFile(filename, "https://github.com/test/file", 1, "a" * 64)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/test",
        "https://untrusted.invalid/file",
        "https://user:pass@github.com/test",
    ],
)
def test_catalog_rejects_unsafe_download_sources(url: str) -> None:
    with pytest.raises(ValueError):
        DownloadFile("model.onnx", url, 1, "a" * 64)


def test_unknown_models_and_invalid_identifiers_cannot_remove_directories(
    tmp_path: Path, model_manifest: ModelManifest
) -> None:
    manager = ModelManager(tmp_path, (model_manifest,), fixture_opener)
    with pytest.raises(ValueError, match="Unknown model"):
        manager.remove("../outside")
    with pytest.raises(ValueError, match="safe directory"):
        replace(model_manifest, model_id="../outside")
    assert list(tmp_path.iterdir()) == []
