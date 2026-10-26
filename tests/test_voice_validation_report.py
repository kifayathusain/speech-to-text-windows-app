"""Long real-model checks resume only against complete, matching evidence."""

import asyncio
import json
import wave
from pathlib import Path

import pytest

from scripts.validate_english_voices import check_provider, read_completed_report
from ttsapp.providers.base import SynthesisRequest, SynthesisResult, VoiceMetadata


@pytest.mark.parametrize(
    "problem", [None, "catalog", "missing-speaker", "unknown-model"]
)
def test_completed_report_requires_matching_catalog_and_all_model_speakers(
    tmp_path: Path, problem: str | None
) -> None:
    report = {
        "catalog_sha256": "expected",
        "results": {"piper-lessac-low": [{"voice_id": "en_US-lessac-low"}]},
    }
    if problem == "catalog":
        report["catalog_sha256"] = "different"
    elif problem == "missing-speaker":
        report["results"]["piper-lessac-low"] = []
    elif problem == "unknown-model":
        report["results"]["unknown"] = []
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    if problem is None:
        assert read_completed_report(path, "expected") == report
    else:
        with pytest.raises(ValueError):
            read_completed_report(path, "expected")


def test_validation_speaks_requested_sample_and_releases_provider(
    tmp_path: Path,
) -> None:
    class Provider:
        closed = False
        request: SynthesisRequest | None = None

        def get_available_voices(self) -> tuple[VoiceMetadata, ...]:
            return (VoiceMetadata("sample", "Sample", "en-US"),)

        async def synthesize(
            self, request: SynthesisRequest, output: Path
        ) -> SynthesisResult:
            self.request = request
            with wave.open(str(output), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(b"\x01\x00" * 100)
            return SynthesisResult(output, "wav")

        def close(self) -> None:
            self.closed = True

    provider = Provider()
    results = asyncio.run(check_provider(provider, tmp_path / "sample.wav", "Hello."))
    assert provider.closed
    assert provider.request.text == "Hello."
    assert results[0]["sample_text"] == "Hello."
    assert results[0]["seconds"] > 0
    assert (tmp_path / results[0]["file"]).is_file()
