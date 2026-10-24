"""Locate optional media binaries shipped beside a frozen Windows application."""

import hashlib
import json
import os
import sys
from pathlib import Path


def configure_bundled_media() -> None:
    """Prepend only integrity-checked packaged tools; source runs retain PATH."""
    if not getattr(sys, "frozen", False):
        return
    directory = Path(sys.executable).resolve().parent / "tools"
    if not directory.exists():
        return
    manifest = json.loads((directory / "sha256.json").read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict):
        raise ValueError("Packaged media manifest must contain file hashes.")
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        digest = hashlib.sha256()
        with (directory / name).open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != manifest.get(name):
            raise ValueError(f"Packaged {name} failed integrity verification.")
    os.environ["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")
