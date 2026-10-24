"""Validate explicitly configured local model assets before loading them."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .catalog import ModelManifest


class ModelValidationError(ValueError):
    """A required model asset is missing, incomplete, or corrupted."""


@dataclass(frozen=True)
class ModelAsset:
    """An explicit file with a trusted, independently obtained SHA-256 digest."""

    path: Path
    sha256: str

    def __post_init__(self) -> None:
        if len(self.sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.sha256
        ):
            raise ValueError("Model assets require a lowercase SHA-256 digest.")

    def validate(self) -> None:
        """Check file existence and integrity without loading or executing it."""
        if not self.path.is_file():
            raise ModelValidationError(f"Required model asset is missing: {self.path}")
        digest = hashlib.sha256()
        with self.path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != self.sha256:
            raise ModelValidationError(
                f"Model asset checksum mismatch; reinstall: {self.path}"
            )


def assets_from_manifest(
    manifest: ModelManifest, directory: Path
) -> dict[str, ModelAsset]:
    """Build explicit asset descriptors from the same trusted installer catalog."""
    return {
        asset.filename: ModelAsset(directory / asset.filename, asset.sha256)
        for asset in manifest.files
    }
