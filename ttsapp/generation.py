"""Chunk orchestration, lossless pauses, and auditable generation metadata."""

import asyncio
import hashlib
import json
import logging
import os
import tempfile
import uuid
import wave
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import Literal

from . import audio_combiner
from .audio_export import (
    ExportProgressCallback,
    ExportSettings,
    export_audio,
    validate_export_target,
)
from .audio_files import write_silence
from .parser import ConversationLine
from .providers.base import CancellationToken, SynthesisRequest, TTSProvider
from .text_processing import (
    SpeechChunk,
    TextProcessingSettings,
    chunk_conversation,
    normalize_text,
)
from .workers import run_blocking_work

logger = logging.getLogger(__name__)
ChunkProgressCallback = Callable[[int, int, SpeechChunk], None]
LineProgressCallback = Callable[[int, int, ConversationLine], None]


@dataclass
class ChunkRecord:
    """A normalized source span and output identity, without recording private text."""

    index: int
    dialogue_index: int
    voice_id: str
    source_start: int
    source_end: int
    text_sha256: str
    output_filename: str
    state: Literal["pending", "running", "done", "failed", "cancelled"] = "pending"
    audio_sha256: str | None = None


@dataclass
class GenerationRecord:
    """Versioned evidence for future safe resumption; no implicit audio reuse."""

    schema_version: int
    provider_id: str
    request_sha256: str
    settings: TextProcessingSettings
    speed: float | None
    export_settings: ExportSettings | None
    chunks: list[ChunkRecord]
    state: Literal["running", "done", "failed", "cancelled"] = "running"


def _text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_record(record: GenerationRecord, destination: Path) -> None:
    """Atomically update job state, so interruptions cannot leave partial JSON."""
    descriptor, name = tempfile.mkstemp(prefix=".metadata-", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.write_text(json.dumps(asdict(record), indent=2), encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _initial_record(
    lines: list[ConversationLine],
    provider: TTSProvider,
    settings: TextProcessingSettings,
    chunks: tuple[SpeechChunk, ...],
    speed: float | None,
    export_settings: ExportSettings | None,
) -> GenerationRecord:
    request_identity = {
        "provider": provider.provider_id,
        "voices": [asdict(voice) for voice in provider.get_available_voices()],
        "settings": asdict(settings),
        "speed": speed,
        "export": asdict(export_settings) if export_settings is not None else None,
        "source": [
            {
                "original_sha256": _text_digest(line.text),
                "normalized_sha256": _text_digest(normalize_text(line.text)),
                "voice": line.voice,
                "paragraph_break_before": line.paragraph_break_before,
            }
            for line in lines
        ],
    }
    return GenerationRecord(
        schema_version=1,
        provider_id=provider.provider_id,
        request_sha256=_text_digest(json.dumps(request_identity, sort_keys=True)),
        settings=settings,
        speed=speed,
        export_settings=export_settings,
        chunks=[
            ChunkRecord(
                index=chunk.index,
                dialogue_index=chunk.dialogue_index,
                voice_id=chunk.voice_id,
                source_start=chunk.source_start,
                source_end=chunk.source_end,
                text_sha256=_text_digest(chunk.text),
                output_filename=f"chunk_{chunk.index:05d}.wav",
            )
            for chunk in chunks
        ],
    )


async def _synthesize_chunk(
    chunk: SpeechChunk,
    provider: TTSProvider,
    native_format: str,
    output: Path,
    token: CancellationToken,
    speed: float | None,
) -> None:
    native_output = output.with_suffix(f".{native_format}")
    result = await provider.synthesize(
        SynthesisRequest(
            chunk.text, chunk.voice_id, audio_format=native_format, speed=speed
        ),
        native_output,
        token,
    )
    if result.output_file != native_output or result.audio_format != native_format:
        raise ValueError("Provider result did not match the requested native output.")
    if native_format == "mp3":
        await run_blocking_work(
            partial(audio_combiner.decode_to_wav, native_output, output), token
        )
    with wave.open(str(output), "rb") as audio:
        if audio.getnframes() == 0:
            raise ValueError("Provider produced an empty audio chunk.")


async def generate_processed_conversation(
    lines: list[ConversationLine],
    provider: TTSProvider,
    *,
    native_format: str,
    output_dir: Path,
    final_audio: Path,
    settings: TextProcessingSettings,
    cancellation_token: CancellationToken | None,
    on_progress: LineProgressCallback | None,
    on_chunk_progress: ChunkProgressCallback | None,
    speed: float | None = None,
    export_settings: ExportSettings | None = None,
    on_export_progress: ExportProgressCallback | None = None,
) -> Path:
    """Generate an isolated, tracked job with complete ordered lossless chunks."""
    token = cancellation_token or CancellationToken()
    token.raise_if_cancelled()
    chunks = chunk_conversation(
        lines, settings, provider.get_capabilities().max_text_characters
    )
    if export_settings is not None:
        validate_export_target(final_audio, export_settings)
    elif final_audio.suffix.lower() not in {".mp3", ".wav"}:
        raise ValueError("Processed audio currently supports MP3 or WAV output.")
    for chunk in chunks:
        provider.validate_configuration(
            SynthesisRequest(
                chunk.text, chunk.voice_id, audio_format=native_format, speed=speed
            )
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    job_directory = output_dir / f"job-{uuid.uuid4().hex}"
    job_directory.mkdir()
    record = _initial_record(lines, provider, settings, chunks, speed, export_settings)
    metadata_file = job_directory / "generation.json"
    _write_record(record, metadata_file)
    audio_files: list[Path] = []
    try:
        for offset, chunk in enumerate(chunks):
            token.raise_if_cancelled()
            item = record.chunks[offset]
            item.state = "running"
            _write_record(record, metadata_file)
            output = job_directory / item.output_filename
            await _synthesize_chunk(
                chunk, provider, native_format, output, token, speed
            )
            if chunk.pause_before_seconds > 0 and audio_files:
                with wave.open(str(output)) as audio:
                    sample_rate = audio.getframerate()
                silence = job_directory / f"pause_{chunk.index:05d}.wav"
                write_silence(silence, sample_rate, chunk.pause_before_seconds, token)
                audio_files.append(silence)
            audio_files.append(output)
            item.audio_sha256 = _file_digest(output)
            item.state = "done"
            _write_record(record, metadata_file)
            if on_chunk_progress is not None:
                on_chunk_progress(chunk.index, len(chunks), chunk)
            last_for_line = (
                offset + 1 == len(chunks)
                or chunks[offset + 1].dialogue_index != chunk.dialogue_index
            )
            if last_for_line and on_progress is not None:
                line = lines[chunk.dialogue_index - 1]
                on_progress(line.index, len(lines), line)
        token.raise_if_cancelled()
        if export_settings is not None:
            result = await run_blocking_work(
                partial(
                    export_audio,
                    audio_files,
                    final_audio,
                    export_settings,
                    on_progress=on_export_progress,
                ),
                token,
            )
        else:
            result = audio_combiner.combine_audio(
                audio_files,
                job_directory,
                final_audio,
                source_format="wav",
                cancellation_token=token,
            )
        record.state = "done"
        try:
            _write_record(record, metadata_file)
        except OSError as error:
            logger.warning(
                "Audio completed but final metadata update failed: %s", error
            )
        return result
    except asyncio.CancelledError:
        token.cancel()
        record.state = "cancelled"
        for item in record.chunks:
            if item.state == "running":
                item.state = "cancelled"
        raise
    except Exception:
        # A provider failure must remain visible while the job records its state.
        record.state = "failed"
        for item in record.chunks:
            if item.state == "running":
                item.state = "failed"
        raise
    finally:
        if record.state != "done":
            try:
                _write_record(record, metadata_file)
            except OSError as error:
                logger.warning(
                    "Could not persist interrupted generation state: %s", error
                )
