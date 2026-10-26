"""Run exhaustive M11 CPU speech checks using real, verified model assets."""

import argparse
import asyncio
import hashlib
import json
import platform
import socket
import time
import wave
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch

from ttsapp.models.catalog import default_catalog
from ttsapp.models.kokoro_catalog import kokoro_v1_model
from ttsapp.models.manager import InstallationState, ModelManager
from ttsapp.models.piper_catalog import english_models
from ttsapp.providers.base import SynthesisRequest, TTSProvider
from ttsapp.providers.kokoro import KokoroTTSProvider
from ttsapp.providers.piper import PiperTTSProvider


def read_completed_report(path: Path, catalog_identity: str) -> dict[str, Any]:
    """Accept saved checks only for this exact catalog and complete voice lists."""
    report = json.loads(path.read_text("utf-8"))
    if report.get("catalog_sha256") != catalog_identity:
        raise ValueError("Cannot resume checks from a different catalog.")
    inventory = {model.model_id: model.voices for model in default_catalog()}
    for identifier, results in report["results"].items():
        if identifier not in inventory or [
            result["voice_id"] for result in results
        ] != list(inventory[identifier]):
            raise ValueError(f"Incomplete or unknown saved results: {identifier}")
    return report


async def check_provider(
    provider: TTSProvider,
    output: Path,
    sample_text: str = "Hello, this is a voice test.",
) -> list[dict[str, str | int | float]]:
    """Synthesize each choice with Python networking denied and inspect PCM."""
    results = []
    voices = provider.get_available_voices()
    try:
        with (
            patch.object(
                socket, "create_connection", side_effect=AssertionError("offline")
            ),
            patch.object(socket, "getaddrinfo", side_effect=AssertionError("offline")),
            patch.object(
                socket.socket, "connect", side_effect=AssertionError("offline")
            ),
        ):
            for voice in voices:
                suffix = hashlib.sha256(voice.voice_id.encode()).hexdigest()[:12]
                voice_output = output.with_name(f"{output.stem}-{suffix}.wav")
                started = time.perf_counter()
                await provider.synthesize(
                    SynthesisRequest(sample_text, voice.voice_id, "wav"),
                    voice_output,
                )
                with wave.open(str(voice_output)) as audio:
                    frames = audio.getnframes()
                    rate = audio.getframerate()
                    if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
                        raise ValueError(f"Invalid PCM layout: {voice.voice_id}")
                    if frames <= 0 or not any(audio.readframes(frames)):
                        raise ValueError(f"Empty/silent audio: {voice.voice_id}")
                results.append(
                    dict(
                        voice_id=voice.voice_id,
                        sample_text=sample_text,
                        file=voice_output.name,
                        audio_retained=voice == voices[-1],
                        sample_rate=rate,
                        seconds=frames / rate,
                        elapsed=time.perf_counter() - started,
                    )
                )
                if voice != voices[-1]:
                    voice_output.unlink()
    finally:
        provider.close()
    return results


def main() -> None:
    """Download missing Piper assets explicitly, then test all English voices."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--kokoro-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-text", default="Hello, this is a voice test.")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed checks only for an identical catalog.",
    )
    parser.add_argument(
        "--remove-after-check",
        action="store_true",
        help="Remove validated Piper installations from this explicit validation root.",
    )
    args = parser.parse_args()
    if not args.sample_text.strip():
        parser.error("--sample-text must contain speech text")
    args.output.mkdir(parents=True, exist_ok=True)
    manager = ModelManager(args.model_root)
    catalog_identity = hashlib.sha256(
        json.dumps(
            [asdict(model) for model in default_catalog()], sort_keys=True
        ).encode()
    ).hexdigest()
    report = dict(
        catalog_sha256=catalog_identity,
        python=platform.python_version(),
        platform=platform.platform(),
        network="Python DNS and socket connection helpers denied during inference",
        results={},
    )
    if args.resume:
        try:
            report = read_completed_report(
                args.output / "report.json", catalog_identity
            )
        except ValueError as error:
            parser.error(str(error))

    def save() -> None:
        (args.output / "report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )

    if "kokoro-82m-v1" not in report["results"]:
        kokoro = KokoroTTSProvider(kokoro_v1_model(args.kokoro_dir))
        report["results"]["kokoro-82m-v1"] = asyncio.run(
            check_provider(kokoro, args.output / "kokoro.wav", args.sample_text)
        )
        save()
        print("Kokoro: 28 voices passed.", flush=True)
    for manifest in default_catalog():
        if manifest.provider_id != "piper":
            continue
        if manifest.model_id in report["results"]:
            print(f"Reusing completed checks: {manifest.model_id}", flush=True)
            continue
        print(f"Installing/verifying {manifest.model_id}...", flush=True)
        if manager.status(manifest.model_id) != InstallationState.INSTALLED:
            manager.install(manifest.model_id)
        provider = PiperTTSProvider(
            english_models(
                manager.model_directory(manifest.model_id), manifest.model_id
            )
        )
        report["results"][manifest.model_id] = asyncio.run(
            check_provider(
                provider, args.output / f"{manifest.model_id}.wav", args.sample_text
            )
        )
        save()
        if args.remove_after_check:
            manager.remove(manifest.model_id)
        print(
            f"{manifest.model_id}: {len(manifest.voices)} voice(s) passed.", flush=True
        )


if __name__ == "__main__":
    main()
