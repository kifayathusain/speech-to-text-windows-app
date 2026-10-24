"""Verified atomic model installation and removal, independent of desktop UI."""

import json
import logging
import os
import re
import shutil
import threading
import urllib.request
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import BinaryIO

from ..config import APP_NAME
from ..providers.base import CancellationToken
from .assets import ModelAsset, ModelValidationError
from .catalog import ModelManifest, default_catalog

logger = logging.getLogger(__name__)


class InstallationState(str, Enum):
    """Only fully verified installed assets are considered ready for inference."""

    NOT_INSTALLED = "Not installed"
    INSTALLED = "Installed and verified"
    CORRUPT = "Incomplete or corrupted; reinstall"


@dataclass(frozen=True)
class DownloadProgress:
    """Byte progress across all required files of one model installation."""

    filename: str
    downloaded_bytes: int
    total_bytes: int


DownloadOpener = Callable[[str], AbstractContextManager[BinaryIO]]
ProgressCallback = Callable[[DownloadProgress], None]


def default_model_directory() -> Path:
    """Use application-specific user storage without administrator privileges."""
    local_data = os.environ.get("LOCALAPPDATA")
    if local_data:
        base_directory = Path(local_data)
    else:
        base_directory = Path.home() / "AppData" / "Local"
    return base_directory / APP_NAME / "models"


def open_download(url: str) -> AbstractContextManager[BinaryIO]:
    """Open a catalog HTTPS source with a bounded network read timeout."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "Windows-TTS-models/1"}
    )
    return urllib.request.urlopen(request, timeout=30)


class ModelManager:
    """Install explicit manifests atomically; never load assets merely found on disk."""

    def __init__(
        self,
        directory: Path | None = None,
        catalog: tuple[ModelManifest, ...] | None = None,
        opener: DownloadOpener = open_download,
    ) -> None:
        self.directory = (
            directory if directory is not None else default_model_directory()
        )
        manifests = default_catalog() if catalog is None else catalog
        self._catalog = {model.model_id: model for model in manifests}
        if len(self._catalog) != len(manifests):
            raise ValueError("Model IDs must be unique.")
        self._opener = opener
        self._lock = threading.Lock()

    def list_models(self) -> tuple[ModelManifest, ...]:
        """Return supported model metadata without network access or inference."""
        return tuple(self._catalog.values())

    def manifest(self, model_id: str) -> ModelManifest:
        """Resolve a catalog entry instead of accepting an arbitrary directory."""
        try:
            return self._catalog[model_id]
        except KeyError as error:
            raise ValueError(f"Unknown model: '{model_id}'.") from error

    def model_directory(self, model_id: str) -> Path:
        """Return a known contained model path without creating it."""
        self.manifest(model_id)
        return self._contained_directory(model_id)

    def _contained_directory(self, name: str) -> Path:
        """Reject symlinks or any target resolving outside the intended root."""
        target = self.directory / name
        if target.is_symlink() or target.resolve().parent != self.directory.resolve():
            raise ValueError("Model operation target must stay inside model storage.")
        return target

    def _validate_installation(self, model: ModelManifest, directory: Path) -> None:
        """Validate marker identity and every known asset before reporting installed."""
        marker_path = directory / "installed.json"
        if marker_path.is_symlink():
            raise ModelValidationError("Installed manifest cannot be a symlink.")
        marker = json.loads(marker_path.read_text("utf-8"))
        identity = {
            "model_id": model.model_id,
            "version": model.version,
            "provider_id": model.provider_id,
        }
        if not isinstance(marker, dict) or any(
            marker.get(key) != value for key, value in identity.items()
        ):
            raise ModelValidationError(
                "Installed model manifest does not match catalog."
            )
        for asset in model.files:
            path = directory / asset.filename
            if path.is_symlink() or path.resolve().parent != directory.resolve():
                raise ModelValidationError(
                    "Model asset must stay inside its directory."
                )
            if path.stat().st_size != asset.size_bytes:
                raise ModelValidationError("Model asset size does not match catalog.")
            ModelAsset(path, asset.sha256).validate()

    def status(self, model_id: str) -> InstallationState:
        """Verify model integrity; call off the UI thread for large model files."""
        model = self.manifest(model_id)
        with self._lock:
            directory = self.model_directory(model_id)
            if not directory.exists():
                return InstallationState.NOT_INSTALLED
            try:
                self._validate_installation(model, directory)
            except (OSError, ValueError, TypeError):
                return InstallationState.CORRUPT
            return InstallationState.INSTALLED

    def _remove_managed_directory(self, directory: Path) -> None:
        """Recursively remove only a verified immediate child of model storage."""
        checked = self._contained_directory(directory.name)
        if checked.resolve() != directory.resolve():
            raise ValueError("Model removal path did not match the checked target.")
        if checked.exists():
            shutil.rmtree(checked)

    def _download_files(
        self,
        model: ModelManifest,
        staging: Path,
        token: CancellationToken,
        on_progress: ProgressCallback | None,
    ) -> None:
        completed_bytes = 0
        for asset in model.files:
            token.raise_if_cancelled()
            downloaded_bytes = 0
            destination = staging / asset.filename
            with self._opener(asset.url) as source, destination.open("wb") as output:
                while True:
                    token.raise_if_cancelled()
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > asset.size_bytes:
                        raise ModelValidationError(
                            "Downloaded asset exceeds expected size."
                        )
                    output.write(chunk)
                    if on_progress is not None:
                        on_progress(
                            DownloadProgress(
                                asset.filename,
                                completed_bytes + downloaded_bytes,
                                model.size_bytes,
                            )
                        )
            if downloaded_bytes != asset.size_bytes:
                raise ModelValidationError("Download was interrupted or incomplete.")
            ModelAsset(destination, asset.sha256).validate()
            completed_bytes += downloaded_bytes

    @contextmanager
    def _operation_lock(self, model_id: str) -> Iterator[None]:
        """Prevent two processes from activating/removing the same model together."""
        self.directory.mkdir(parents=True, exist_ok=True)
        lock_path = self.directory / f".lock-{model_id}"
        if lock_path.is_symlink():
            raise ValueError("Model operation lock cannot be a symlink.")
        with lock_path.open("a+b") as lock_file:
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                lock_file.seek(0)
                if os.name == "nt":
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _recover_interrupted(self, model: ModelManifest, destination: Path) -> None:
        """Restore verified backups and remove incomplete staging under a job lock."""
        for candidate in self.directory.iterdir():
            if re.fullmatch(
                rf"\.staging-{model.model_id}-[0-9a-f]{{32}}", candidate.name
            ):
                self._remove_managed_directory(candidate)
            elif re.fullmatch(
                rf"\.backup-{model.model_id}-[0-9a-f]{{32}}", candidate.name
            ):
                checked = self._contained_directory(candidate.name)
                if not destination.exists():
                    try:
                        self._validate_installation(model, checked)
                    except (OSError, ValueError, TypeError) as error:
                        logger.warning("Preserving invalid model backup: %s", error)
                    else:
                        os.replace(checked, destination)
                else:
                    self._remove_managed_directory(checked)

    def install(
        self,
        model_id: str,
        cancellation_token: CancellationToken | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> Path:
        """Download, verify all files, and atomically activate a complete model."""
        model = self.manifest(model_id)
        token = cancellation_token or CancellationToken()
        token.raise_if_cancelled()
        with self._lock, self._operation_lock(model_id):
            token.raise_if_cancelled()
            destination = self.model_directory(model_id)
            self._recover_interrupted(model, destination)
            staging = self._contained_directory(
                f".staging-{model_id}-{uuid.uuid4().hex}"
            )
            backup = self._contained_directory(f".backup-{model_id}-{uuid.uuid4().hex}")
            staging.mkdir()
            try:
                self._download_files(model, staging, token, on_progress)
                (staging / "installed.json").write_text(
                    json.dumps(asdict(model), indent=2), encoding="utf-8"
                )
                self._validate_installation(model, staging)
                token.raise_if_cancelled()
                if destination.exists():
                    os.replace(destination, backup)
                try:
                    os.replace(staging, destination)
                except OSError:
                    if backup.exists():
                        os.replace(backup, destination)
                    raise
                self._remove_managed_directory(backup)
                self._recover_interrupted(model, destination)
                return destination
            finally:
                self._remove_managed_directory(staging)

    def remove(self, model_id: str) -> None:
        """Remove only a selected known model, preserving unrelated directories."""
        self.manifest(model_id)
        with self._lock, self._operation_lock(model_id):
            self._remove_managed_directory(self.model_directory(model_id))
