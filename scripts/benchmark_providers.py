"""Measure real Edge/Piper/Kokoro separately; never substitute mock timings."""

import argparse
import asyncio
import json
import math
import platform
import time
import wave
from array import array
from dataclasses import asdict, dataclass
from pathlib import Path

from ttsapp.audio_combiner import decode_to_wav
from ttsapp.audio_export import ExportSettings, export_audio, probe_audio
from ttsapp.models.kokoro_catalog import kokoro_v1_model
from ttsapp.models.piper_catalog import lessac_low_model
from ttsapp.providers.base import CancellationToken, SynthesisRequest, TTSProvider
from ttsapp.providers.edge import EdgeTTSProvider
from ttsapp.providers.kokoro import KokoroTTSProvider
from ttsapp.providers.piper import PiperTTSProvider

SAMPLES = (
    ("short", "Hello. This speech is generated locally on the CPU."),
    (
        "paragraph",
        "The morning train arrived beside the river. We opened the window, checked "
        "our notes, and planned the day. Every voice in this example is generated "
        "on this computer.",
    ),
)


@dataclass
class BenchmarkCase:
    """Observed complete-native-audio timing and objective output measurements."""

    voice: str
    input_label: str
    repetition: int
    characters: int
    status: str = "failed"
    synthesis_seconds: float = 0.0
    audio_seconds: float | None = None
    real_time_factor: float | None = None
    cpu_seconds: float | None = None
    process_cpu_percent: float | None = None
    process_rss_bytes: int | None = None
    process_peak_working_set_bytes: int | None = None
    sample_rate: int | None = None
    pcm_peak: int | None = None
    pcm_rms: float | None = None
    clipped_sample_fraction: float | None = None
    export_seconds: float | None = None
    error: str | None = None


def _provider(
    provider_id: str, model_directory: Path | None, cpu_threads: int, memory_arena: bool
) -> tuple[TTSProvider, tuple[str, ...], str]:
    if provider_id == "edge":
        return EdgeTTSProvider(), ("en-GB-SoniaNeural", "en-GB-RyanNeural"), "mp3"
    if model_directory is None:
        raise ValueError(
            "Local providers require an explicit verified model directory."
        )
    if provider_id == "piper":
        model = lessac_low_model(model_directory)
        return (
            PiperTTSProvider((model,), cpu_threads, memory_arena),
            (model.voice.voice_id,),
            "wav",
        )
    if provider_id == "kokoro":
        return (
            KokoroTTSProvider(
                kokoro_v1_model(model_directory), cpu_threads, memory_arena
            ),
            ("af_heart", "bf_emma"),
            "wav",
        )
    raise ValueError(f"Unknown benchmark provider: '{provider_id}'.")


def _measure_case(
    provider: TTSProvider,
    voice: str,
    label: str,
    text: str,
    native_format: str,
    repetition: int,
    output_directory: Path,
) -> BenchmarkCase:
    import psutil

    process = psutil.Process()
    case = BenchmarkCase(voice, label, repetition, len(text))
    output = output_directory / f"{voice}-{label}-{repetition}.{native_format}"
    request = SynthesisRequest(text, voice, native_format)
    cpu_started = time.process_time()
    started = time.perf_counter()
    synthesis_started = started
    try:
        asyncio.run(asyncio.wait_for(provider.synthesize(request, output), timeout=60))
        case.synthesis_seconds = time.perf_counter() - started
        case.cpu_seconds = time.process_time() - cpu_started
        case.process_cpu_percent = 100 * case.cpu_seconds / case.synthesis_seconds
        token = CancellationToken()
        info = probe_audio(output, token)
        case.audio_seconds = info.duration_seconds
        case.real_time_factor = case.synthesis_seconds / case.audio_seconds
        case.sample_rate = info.sample_rate
        pcm = output
        if native_format == "mp3":
            pcm = output.with_suffix(".decoded.wav")
            decode_to_wav(output, pcm, token)
        with wave.open(str(pcm)) as audio:
            samples = array("h", audio.readframes(audio.getnframes()))
        case.pcm_peak = max(abs(sample) for sample in samples)
        case.pcm_rms = math.sqrt(
            sum(sample * sample for sample in samples) / len(samples)
        )
        case.clipped_sample_fraction = sum(
            abs(sample) >= 32760 for sample in samples
        ) / len(samples)
        started = time.perf_counter()
        export_audio(
            [output],
            output.with_name(output.stem + "-export.mp3"),
            ExportSettings("mp3"),
            token,
        )
        case.export_seconds = time.perf_counter() - started
        memory = process.memory_info()
        case.process_rss_bytes = memory.rss
        case.process_peak_working_set_bytes = getattr(memory, "peak_wset", None)
        case.status = "success"
    except Exception as error:
        if case.synthesis_seconds == 0:
            case.synthesis_seconds = time.perf_counter() - synthesis_started
        case.error = f"{type(error).__name__}: {str(error).split('url=')[0][:400]}"
    return case


def benchmark(
    provider_id: str,
    model_directory: Path | None,
    output_directory: Path,
    cpu_threads: int = 2,
    repetitions: int = 1,
    memory_arena: bool = True,
) -> dict[str, object]:
    """Run native providers, measuring model initialization separately from synthesis."""
    if repetitions < 1:
        raise ValueError("Benchmark repetitions must be positive.")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise ValueError("Use an empty benchmark output directory to preserve results.")
    output_directory.mkdir(parents=True, exist_ok=True)
    provider, voices, native_format = _provider(
        provider_id, model_directory, cpu_threads, memory_arena
    )
    started = time.perf_counter()
    cases = []
    try:
        if isinstance(provider, KokoroTTSProvider):
            provider.prepare()
        elif isinstance(provider, PiperTTSProvider):
            provider.prepare(voices[0])
        load_seconds = time.perf_counter() - started
        for voice in voices:
            for repetition in range(1, repetitions + 1):
                for label, text in SAMPLES:
                    cases.append(
                        _measure_case(
                            provider,
                            voice,
                            label,
                            text,
                            native_format,
                            repetition,
                            output_directory,
                        )
                    )
    finally:
        provider.close()
    first_latency = (
        load_seconds + cases[0].synthesis_seconds
        if cases[0].status == "success"
        else None
    )
    return {
        "provider": provider_id,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_threads": cpu_threads if provider_id != "edge" else None,
        "memory_arena": memory_arena if provider_id != "edge" else None,
        "model_load_and_verification_seconds": load_seconds,
        "first_completed_native_audio_seconds": first_latency,
        "measurement_notes": "Native synthesis includes provider validation/PCM writing, excluding model initialization, analysis, and final export. Peak working set is process-cumulative. Failed cases have no invented RTF. Edge samples use its real online service.",
        "results": [asdict(case) for case in cases],
    }


def main() -> None:
    """Write a real per-provider benchmark report for explicit local/public samples."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider", choices=("edge", "piper", "kokoro"), required=True
    )
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--cpu-threads", type=int, default=2)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--no-memory-arena", action="store_true")
    args = parser.parse_args()
    report = benchmark(
        args.provider,
        args.model_dir,
        args.output_dir,
        args.cpu_threads,
        args.repetitions,
        not args.no_memory_arena,
    )
    destination = args.output_dir / "benchmark.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
