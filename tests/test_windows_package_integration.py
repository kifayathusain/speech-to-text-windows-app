"""Opt-in extracted executable checks with real downloads and isolated user data."""

import json
import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.real_model
@pytest.mark.skipif(
    not os.environ.get("TTS_PACKAGE_EXE"),
    reason="Set TTS_PACKAGE_EXE for an extracted full Windows package/network test.",
)
def test_extracted_package_downloads_and_uses_both_cpu_models(tmp_path: Path) -> None:
    """The executable must supply Python, native runtimes, and bundled media tools."""
    executable = Path(os.environ["TTS_PACKAGE_EXE"]).resolve()
    report_directory = tmp_path / "report"
    models = tmp_path / "models"
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "TCL_LIBRARY", "TK_LIBRARY"):
        environment.pop(name, None)
    windows = Path(environment.get("SystemRoot", "C:/Windows"))
    environment["PATH"] = str(windows / "System32") + os.pathsep + str(windows)
    environment["LOCALAPPDATA"] = str(tmp_path / "profile")
    completed = subprocess.run(
        [
            str(executable),
            "--diagnostics",
            str(report_directory),
            "--model-root",
            str(models),
            "--download-model",
            "kokoro-82m-v1",
            "--download-model",
            "piper-lessac-low",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        timeout=300,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    evidence = report_directory / "acceptance.json"
    assert evidence.is_file(), completed.stderr.decode(errors="replace")
    report = json.loads(evidence.read_text(encoding="utf-8"))
    assert completed.returncode == 0, report
    assert [case["provider"] for case in report["results"]] == ["kokoro", "piper"]
    assert all(case["status"] == "passed" for case in report["results"])
    for case in report["results"]:
        assert {export["codec"] for export in case["exports"]} == {
            "pcm_s16le",
            "mp3",
            "aac",
        }
    assert (models / "kokoro-82m-v1" / "installed.json").is_file()
    assert (models / "piper-lessac-low" / "installed.json").is_file()
    assert report["clean_machine_confirmed"] is False
