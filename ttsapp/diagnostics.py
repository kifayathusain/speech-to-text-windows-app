"""Explicit portable-package acceptance checks with fixed public sample text."""

import argparse
import asyncio
import json
import platform
import time
from pathlib import Path

from .audio_export import ExportSettings, export_audio, probe_audio
from .models.manager import ModelManager
from .provider_manager import ProviderManager
from .providers.base import CancellationToken, SynthesisRequest
from .runtime_paths import configure_bundled_media


def check_provider(
    providers: ProviderManager, identifier: str, output: Path
) -> dict[str, object]:
    """Use the real selected runtime and validate all supported final containers."""
    provider = providers.get(identifier)
    voice = provider.get_available_voices()[0]
    audio_format = "mp3" if identifier == "edge" else "wav"
    native = output / f"{identifier}-native.{audio_format}"
    started = time.perf_counter()
    asyncio.run(
        provider.synthesize(
            SynthesisRequest(
                "Hello. This is the Windows text to speech acceptance sample.",
                voice.voice_id,
                audio_format,
            ),
            native,
        )
    )
    elapsed = time.perf_counter() - started
    exports = []
    for container in ("wav", "mp3", "m4a"):
        path = output / f"{identifier}-export.{container}"
        export_audio([native], path, ExportSettings(container), CancellationToken())
        info = probe_audio(path, CancellationToken())
        exports.append(
            {
                "file": path.name,
                "codec": info.codec,
                "duration_seconds": info.duration_seconds,
                "sample_rate": info.sample_rate,
            }
        )
    return {
        "provider": identifier,
        "status": "passed",
        "voice": voice.voice_id,
        "native_synthesis_seconds": elapsed,
        "exports": exports,
    }


def main(arguments: list[str]) -> int:
    """Write a reviewable acceptance report, requiring explicit model downloads."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostics", required=True, type=Path)
    parser.add_argument("--model-root", type=Path)
    parser.add_argument(
        "--download-model",
        action="append",
        choices=("kokoro-82m-v1", "piper-lessac-low"),
        default=[],
    )
    parser.add_argument("--check-edge", action="store_true")
    args = parser.parse_args(arguments)
    output = args.diagnostics.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("Use an empty diagnostics directory to preserve earlier results.")
    output.mkdir(parents=True, exist_ok=True)
    models = ModelManager(args.model_root)
    providers = ProviderManager(models)
    results = []
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "model_directory": str(models.directory),
        "results": results,
        "clean_machine_confirmed": False,
        "notes": "This command cannot establish that the host is a clean machine.",
    }
    try:
        configure_bundled_media()
        for identifier in args.download_model:
            models.install(identifier)
        identifiers = ["kokoro", "piper"]
        if args.check_edge:
            identifiers.append("edge")
        for identifier in identifiers:
            try:
                results.append(check_provider(providers, identifier, output))
            except Exception as error:
                results.append(
                    {
                        "provider": identifier,
                        "status": "failed",
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
    except Exception as error:
        results.append({"stage": "setup", "status": "failed", "error": str(error)})
    finally:
        providers.close()
        (output / "acceptance.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    return int(any(result["status"] != "passed" for result in results))
