"""Packaged media selection preserves source behavior and rejects changed tools."""

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from ttsapp.runtime_paths import configure_bundled_media


def test_source_launch_preserves_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("PATH", "original")
    configure_bundled_media()
    assert os.environ["PATH"] == "original"


@pytest.mark.parametrize("corrupted", [False, True])
def test_packaged_tools_require_matching_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corrupted: bool
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "WindowsTTSApp.exe"))
    monkeypatch.setenv("PATH", "original")
    directory = tmp_path / "tools"
    directory.mkdir()
    hashes = {}
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        data = name.encode()
        (directory / name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    (directory / "sha256.json").write_text(json.dumps(hashes), encoding="utf-8-sig")
    if corrupted:
        (directory / "ffprobe.exe").write_bytes(b"changed")
        with pytest.raises(ValueError, match="integrity"):
            configure_bundled_media()
        assert os.environ["PATH"] == "original"
    else:
        configure_bundled_media()
        assert os.environ["PATH"] == str(directory) + os.pathsep + "original"


def test_external_tools_remain_available_without_bundled_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "WindowsTTSApp.exe"))
    monkeypatch.setenv("PATH", "original")
    configure_bundled_media()
    assert os.environ["PATH"] == "original"
