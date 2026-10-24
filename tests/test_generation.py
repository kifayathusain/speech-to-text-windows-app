"""Processed jobs preserve ordered source spans, pauses, and interruption evidence."""

import asyncio
import hashlib
import json
import threading
import time
from pathlib import Path

import pytest

from ttsapp import generation
from ttsapp.audio_export import ExportSettings
from ttsapp.audio_files import write_pcm_wav
from ttsapp.providers.base import (
    CancellationToken,
    ProviderCapabilities,
    SynthesisRequest,
    SynthesisResult,
    VoiceMetadata,
)
from ttsapp.service import generate_conversation
from ttsapp.text_processing import TextProcessingSettings


class OfflineProvider:
    """Controlled PCM provider for observable orchestration behavior."""

    provider_id = "offline-test"
    display_name = "Offline test"

    def __init__(self) -> None:
        self.requests: list[SynthesisRequest] = []
        self.fail_on_call: int | None = None
        self.cancel_on_call: int | None = None

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            online=False, audio_formats=("wav",), max_text_characters=80
        )

    def get_available_voices(self) -> tuple[VoiceMetadata, ...]:
        return (VoiceMetadata("voice", "Test", "en-US"),)

    def validate_configuration(self, request: SynthesisRequest) -> None:
        if len(request.text) > 80 or "REJECT" in request.text:
            raise ValueError("Invalid test request")

    async def synthesize(
        self,
        request: SynthesisRequest,
        output_file: Path,
        cancellation_token: CancellationToken | None = None,
    ) -> SynthesisResult:
        self.requests.append(request)
        if len(self.requests) == self.fail_on_call:
            raise RuntimeError("Inference failed")
        if len(self.requests) == self.cancel_on_call:
            raise asyncio.CancelledError
        write_pcm_wav(
            (b"\x01\x00" * 100,),
            output_file,
            16000,
            cancellation_token or CancellationToken(),
        )
        return SynthesisResult(output_file, "wav")


@pytest.fixture
def combined_files(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    inputs: list[Path] = []

    def combine(files: list[Path], parts: Path, final: Path, **kwargs: object) -> Path:
        inputs.extend(files)
        final.write_bytes(b"combined")
        return final

    monkeypatch.setattr(generation.audio_combiner, "combine_audio", combine)
    return inputs


def test_long_generation_preserves_every_source_character_and_progress(
    tmp_path: Path, combined_files: list[Path]
) -> None:
    provider = OfflineProvider()
    text = ("Dr. Smith paid $3.14. Next sentence! " * 100).strip()
    lines_completed: list[int] = []
    chunks_completed: list[int] = []
    result = asyncio.run(
        generate_conversation(
            input_text=f"Caller: {text}",
            voices={"Caller": "voice"},
            provider_id=provider.provider_id,
            provider=provider,
            output_dir=tmp_path / "parts",
            final_audio=tmp_path / "final.wav",
            on_progress=lambda index, total, line: lines_completed.append(index),
            on_chunk_progress=lambda index, total, chunk: chunks_completed.append(
                index
            ),
        )
    )

    assert result.read_bytes() == b"combined"
    assert "".join(request.text for request in provider.requests) == text
    assert all(len(request.text) <= 80 for request in provider.requests)
    assert lines_completed == [1]
    assert chunks_completed == list(range(1, len(provider.requests) + 1))
    metadata_file = next((tmp_path / "parts").glob("job-*/generation.json"))
    metadata = json.loads(metadata_file.read_text())
    assert metadata["state"] == "done"
    assert all(chunk["state"] == "done" for chunk in metadata["chunks"])
    assert text not in metadata_file.read_text()
    assert len(combined_files) == len(provider.requests)
    for record, output in zip(metadata["chunks"], combined_files, strict=True):
        assert record["audio_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


def test_paragraph_pause_is_lossless_exact_and_only_between_paragraphs(
    tmp_path: Path, combined_files: list[Path]
) -> None:
    import wave

    provider = OfflineProvider()
    asyncio.run(
        generate_conversation(
            input_text="Caller: First.\n\nCaller: Second.",
            voices={"Caller": "voice"},
            provider_id=provider.provider_id,
            provider=provider,
            output_dir=tmp_path / "parts",
            final_audio=tmp_path / "final.wav",
        )
    )

    assert [file.name for file in combined_files] == [
        "chunk_00001.wav",
        "pause_00002.wav",
        "chunk_00002.wav",
    ]
    with wave.open(str(combined_files[1])) as silence:
        assert silence.getnframes() == 5600
        assert set(silence.readframes(5600)) == {0}


@pytest.mark.parametrize("cancel", [False, True])
def test_failed_or_cancelled_job_preserves_export_and_records_completed_chunks(
    tmp_path: Path, combined_files: list[Path], cancel: bool
) -> None:
    provider = OfflineProvider()
    if cancel:
        provider.cancel_on_call = 2
    else:
        provider.fail_on_call = 2
    final = tmp_path / "final.wav"
    final.write_bytes(b"previous")
    expected = asyncio.CancelledError if cancel else RuntimeError

    with pytest.raises(expected):
        asyncio.run(
            generate_conversation(
                input_text="Caller: " + "Sentence. " * 20,
                voices={"Caller": "voice"},
                provider_id=provider.provider_id,
                provider=provider,
                output_dir=tmp_path / "parts",
                final_audio=final,
            )
        )

    assert final.read_bytes() == b"previous"
    assert combined_files == []
    metadata = json.loads(
        next((tmp_path / "parts").glob("job-*/generation.json")).read_text()
    )
    assert metadata["state"] == ("cancelled" if cancel else "failed")
    assert metadata["chunks"][0]["state"] == "done"
    assert metadata["chunks"][1]["state"] == ("cancelled" if cancel else "failed")
    assert not list((tmp_path / "parts").rglob(".metadata-*"))


def test_all_chunks_validate_before_output_side_effects(tmp_path: Path) -> None:
    provider = OfflineProvider()
    with pytest.raises(ValueError, match="Invalid test request"):
        asyncio.run(
            generate_conversation(
                input_text="Caller: Valid. REJECT this request.",
                voices={"Caller": "voice"},
                provider_id=provider.provider_id,
                provider=provider,
                output_dir=tmp_path / "parts",
                final_audio=tmp_path / "final.wav",
            )
        )
    assert list(tmp_path.iterdir()) == []
    assert provider.requests == []


def test_repeated_jobs_have_isolated_chunks(
    tmp_path: Path, combined_files: list[Path]
) -> None:
    provider = OfflineProvider()
    for text in ("First job.", "Second job."):
        asyncio.run(
            generate_conversation(
                input_text=f"Caller: {text}",
                voices={"Caller": "voice"},
                provider_id=provider.provider_id,
                provider=provider,
                output_dir=tmp_path / "parts",
                final_audio=tmp_path / "final.wav",
            )
        )
    assert len(list((tmp_path / "parts").glob("job-*"))) == 2
    assert combined_files[0].parent != combined_files[1].parent


def test_final_metadata_failure_does_not_misreport_successful_audio_as_failed(
    tmp_path: Path,
    combined_files: list[Path],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = OfflineProvider()
    original_write = generation._write_record

    def write(record: generation.GenerationRecord, path: Path) -> None:
        if record.state == "done":
            raise OSError("metadata disk failure")
        original_write(record, path)

    monkeypatch.setattr(generation, "_write_record", write)
    result = asyncio.run(
        generate_conversation(
            input_text="Caller: Hello.",
            voices={"Caller": "voice"},
            provider_id=provider.provider_id,
            provider=provider,
            output_dir=tmp_path / "parts",
            final_audio=tmp_path / "final.wav",
        )
    )

    assert result.read_bytes() == b"combined"
    assert "Audio completed but final metadata update failed" in caplog.text


def test_processed_online_audio_is_decoded_before_lossless_pauses_and_export(
    tmp_path: Path,
    combined_files: list[Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decoded_sources: list[Path] = []

    class OnlineProvider(OfflineProvider):
        def get_capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(online=True, audio_formats=("mp3",))

        async def synthesize(
            self,
            request: SynthesisRequest,
            output_file: Path,
            cancellation_token: CancellationToken | None = None,
        ) -> SynthesisResult:
            self.requests.append(request)
            output_file.write_bytes(b"native MP3")
            return SynthesisResult(output_file, "mp3")

    def decode(source: Path, destination: Path, token: CancellationToken) -> None:
        decoded_sources.append(source)
        assert source.read_bytes() == b"native MP3"
        write_pcm_wav((b"\x01\x00" * 100,), destination, 16000, token)

    monkeypatch.setattr(generation.audio_combiner, "decode_to_wav", decode)
    provider = OnlineProvider()
    asyncio.run(
        generate_conversation(
            input_text="Caller: First.\n\nCaller: Second.",
            voices={"Caller": "voice"},
            provider_id=provider.provider_id,
            provider=provider,
            output_dir=tmp_path / "parts",
            final_audio=tmp_path / "final.wav",
            text_settings=TextProcessingSettings(),
        )
    )

    assert len(decoded_sources) == 2
    assert all(source.suffix == ".mp3" for source in decoded_sources)
    assert len(combined_files) == 3
    assert all(file.suffix == ".wav" for file in combined_files)


def test_selected_speed_reaches_every_chunk_and_job_metadata(
    tmp_path: Path, combined_files: list[Path]
) -> None:
    provider = OfflineProvider()
    asyncio.run(
        generate_conversation(
            input_text="Caller: " + "Sentence. " * 20,
            voices={"Caller": "voice"},
            provider_id=provider.provider_id,
            provider=provider,
            speed=0.8,
            output_dir=tmp_path / "parts",
            final_audio=tmp_path / "final.wav",
        )
    )
    assert provider.requests and all(
        request.speed == 0.8 for request in provider.requests
    )
    metadata = json.loads(
        next((tmp_path / "parts").glob("job-*/generation.json")).read_text()
    )
    assert metadata["speed"] == 0.8


def test_async_cancellation_during_export_records_cancelled_and_preserves_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = OfflineProvider()
    started = threading.Event()
    final = tmp_path / "final.m4a"
    final.write_bytes(b"previous")

    def export(
        files: list[Path],
        output: Path,
        settings: ExportSettings,
        token: CancellationToken,
        **kwargs: object,
    ) -> Path:
        started.set()
        while not token.is_cancelled:
            time.sleep(0.01)
        raise asyncio.CancelledError

    monkeypatch.setattr(generation, "export_audio", export)

    async def exercise() -> None:
        task = asyncio.create_task(
            generate_conversation(
                input_text="Caller: Hello.",
                voices={"Caller": "voice"},
                provider_id=provider.provider_id,
                provider=provider,
                output_dir=tmp_path / "parts",
                final_audio=final,
                export_settings=ExportSettings("m4a", overwrite=True),
            )
        )
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=3)

    asyncio.run(exercise())
    assert final.read_bytes() == b"previous"
    metadata = json.loads(
        next((tmp_path / "parts").glob("job-*/generation.json")).read_text()
    )
    assert metadata["state"] == "cancelled"
