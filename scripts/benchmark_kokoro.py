"""Measure real Kokoro CPU inference and objective audio checks; no downloads."""

import argparse
import asyncio
import json
import math
import platform
import time
import wave
from array import array
from pathlib import Path

from ttsapp.audio_combiner import combine_audio
from ttsapp.models.kokoro_catalog import kokoro_v1_model
from ttsapp.providers.base import SynthesisRequest
from ttsapp.providers.kokoro import KokoroTTSProvider


def benchmark(
    model_directory: Path, output_directory: Path, threads: int
) -> dict[str, object]:
    """Record measured load, synthesis, export, process resources, and PCM levels."""
    import psutil

    output_directory.mkdir(parents=True, exist_ok=True)
    process = psutil.Process()
    provider = KokoroTTSProvider(kokoro_v1_model(model_directory), threads)
    results: list[dict[str, object]] = []
    first_completed_audio_seconds = 0.0
    started = time.perf_counter()
    try:
        provider.prepare()
        load_seconds = time.perf_counter() - started
        for voice_id in ("af_heart", "bf_emma"):
            for label, text in (
                ("short", "Hello. This speech is generated locally on the CPU."),
                (
                    "paragraph",
                    "The morning train arrived beside the river. We opened the "
                    "window, checked our notes, and planned the day. Every voice "
                    "in this example is generated on this computer.",
                ),
            ):
                output = output_directory / f"{voice_id}-{label}.wav"
                request = SynthesisRequest(text, voice_id, "wav")
                cpu_started = time.process_time()
                started = time.perf_counter()
                asyncio.run(provider.synthesize(request, output))
                synthesis_seconds = time.perf_counter() - started
                if not results:
                    first_completed_audio_seconds = load_seconds + synthesis_seconds
                cpu_seconds = time.process_time() - cpu_started
                with wave.open(str(output)) as audio:
                    duration = audio.getnframes() / audio.getframerate()
                    samples = array("h", audio.readframes(audio.getnframes()))
                    sample_rate = audio.getframerate()
                started = time.perf_counter()
                combine_audio(
                    [output],
                    output_directory,
                    output.with_suffix(".mp3"),
                    source_format="wav",
                )
                export_seconds = time.perf_counter() - started
                memory = process.memory_info()
                results.append(
                    {
                        "voice": voice_id,
                        "input": label,
                        "characters": len(text),
                        "synthesis_seconds": synthesis_seconds,
                        "audio_seconds": duration,
                        "real_time_factor": synthesis_seconds / duration,
                        "cpu_seconds": cpu_seconds,
                        "process_cpu_percent": 100 * cpu_seconds / synthesis_seconds,
                        "process_rss_bytes": memory.rss,
                        "process_peak_working_set_bytes": getattr(
                            memory, "peak_wset", None
                        ),
                        "sample_rate": sample_rate,
                        "pcm_peak": max(abs(sample) for sample in samples),
                        "pcm_rms": math.sqrt(
                            sum(sample * sample for sample in samples) / len(samples)
                        ),
                        "clipped_sample_fraction": sum(
                            abs(sample) >= 32760 for sample in samples
                        )
                        / len(samples),
                        "export_seconds": export_seconds,
                    }
                )
    finally:
        provider.close()
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_threads": threads,
        "model_load_and_verification_seconds": load_seconds,
        "first_completed_audio_seconds": first_completed_audio_seconds,
        "measurement_notes": (
            "Synthesis includes provider validation and PCM writing, excluding "
            "model initialization and export. Process peak working set is cumulative. "
            "PCM checks do not establish naturalness; human listening remains separate."
        ),
        "results": results,
    }


def main() -> None:
    """Run explicit local assets and save a reproducible benchmark report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cpu-threads", type=int, default=2)
    arguments = parser.parse_args()
    report = benchmark(arguments.model_dir, arguments.output_dir, arguments.cpu_threads)
    destination = arguments.output_dir / "benchmark.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
