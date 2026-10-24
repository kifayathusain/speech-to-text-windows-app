"""Portable QA reports failures explicitly and preserves earlier evidence."""

import json
from pathlib import Path

import pytest

from ttsapp import diagnostics


def test_diagnostics_records_missing_models_and_cleans_provider_lifecycle(
    tmp_path: Path,
) -> None:
    output = tmp_path / "report"
    result = diagnostics.main(
        ["--diagnostics", str(output), "--model-root", str(tmp_path / "models")]
    )
    assert result == 1
    report = json.loads((output / "acceptance.json").read_text())
    assert report["clean_machine_confirmed"] is False
    assert len(report["results"]) == 2
    assert all(case["status"] == "failed" for case in report["results"])
    assert not (tmp_path / "models").exists()


def test_diagnostics_never_overwrites_previous_report(tmp_path: Path) -> None:
    evidence = tmp_path / "acceptance.json"
    evidence.write_text("previous")
    with pytest.raises(SystemExit) as error:
        diagnostics.main(["--diagnostics", str(tmp_path)])
    assert error.value.code == 2
    assert evidence.read_text() == "previous"


def test_diagnostics_reports_media_setup_failure_without_opening_a_dialog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable() -> None:
        raise ValueError("Packaged media integrity failure")

    monkeypatch.setattr(diagnostics, "configure_bundled_media", unavailable)
    assert diagnostics.main(["--diagnostics", str(tmp_path)]) == 1
    report = json.loads((tmp_path / "acceptance.json").read_text())
    assert report["results"] == [
        {
            "stage": "setup",
            "status": "failed",
            "error": "Packaged media integrity failure",
        }
    ]
