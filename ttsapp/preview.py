"""Bounded real-voice previews, cache identity, and native Windows playback."""

import hashlib
import json
import os
import re
import tempfile
import wave
from functools import partial
from pathlib import Path
from typing import Protocol

from .audio_combiner import decode_to_wav
from .models.manager import default_model_directory
from .providers.base import CancellationToken, SynthesisRequest, TTSProvider
from .text_processing import normalize_text, split_text
from .workers import run_blocking_work

SAMPLE_TEXT = "Hello. This is a preview of the selected voice."


class PreviewProviderSource(Protocol):
    """Provider/session dependencies required by the preview service."""

    def get(self, provider_id: str) -> TTSProvider:
        """Resolve the selected provider and its verified prerequisites."""
        ...

    def cache_identity(self, provider_id: str) -> str:
        """Identify the provider/model version represented by cached speech."""
        ...


def strip_speaker_labels(text: str, speakers: set[str]) -> str:
    """Remove only known script labels while retaining ordinary colons and dates."""
    lines = []
    for line in text.splitlines():
        if ":" in line:
            speaker, dialogue = line.split(":", 1)
            if speaker.strip() in speakers:
                line = dialogue
        lines.append(line)
    return "\n".join(lines)


def build_preview_text(selected_text: str | None) -> str:
    """Use a short actual selection or a stable sample without splitting clusters."""
    text = normalize_text(selected_text if selected_text else SAMPLE_TEXT)
    if not text:
        raise ValueError("Preview text cannot be empty.")
    start, end = split_text(text, 400)[0]
    return text[start:end]


class PreviewService:
    """Synthesize selected voice/speed and retain only a bounded verified PCM cache."""

    def __init__(
        self,
        providers: PreviewProviderSource,
        directory: Path | None = None,
        max_entries: int = 8,
    ) -> None:
        if max_entries < 1:
            raise ValueError("Preview cache size must be positive.")
        self._providers = providers
        self.directory = (
            directory
            if directory is not None
            else default_model_directory().parent / "previews"
        )
        self._max_entries = max_entries

    @staticmethod
    def _valid_audio(path: Path) -> bool:
        if not path.is_file() or path.is_symlink():
            return False
        try:
            with wave.open(str(path)) as audio:
                return (
                    audio.getnframes() > 0
                    and audio.getsampwidth() == 2
                    and audio.getnchannels() == 1
                )
        except (OSError, wave.Error, EOFError):
            return False

    def _trim_cache(self, current: Path) -> None:
        candidates = sorted(
            (
                path
                for path in self.directory.iterdir()
                if re.fullmatch(r"[0-9a-f]{64}\.wav", path.name)
                and path.is_file()
                and not path.is_symlink()
            ),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        retained = 1
        for path in candidates:
            if path == current:
                continue
            if retained >= self._max_entries:
                path.unlink()
            else:
                retained += 1

    async def generate(
        self,
        provider_id: str,
        voice_id: str,
        selected_text: str | None,
        speed: float | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> Path:
        """Generate a short preview without downloading or selecting another engine."""
        token = cancellation_token or CancellationToken()
        token.raise_if_cancelled()
        text = build_preview_text(selected_text)
        provider = self._providers.get(provider_id)
        native_format = (
            "wav" if "wav" in provider.get_capabilities().audio_formats else "mp3"
        )
        request = SynthesisRequest(text, voice_id, native_format, speed=speed)
        provider.validate_configuration(request)
        identity = {
            "provider": self._providers.cache_identity(provider_id),
            "voice": voice_id,
            "text": text,
            "speed": speed,
        }
        filename = (
            hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            + ".wav"
        )
        output = self.directory / filename
        token.raise_if_cancelled()
        if self._valid_audio(output):
            output.touch()
            return output
        self.directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".preview-", dir=self.directory
        ) as temporary:
            native_output = Path(temporary) / f"native.{native_format}"
            result = await provider.synthesize(request, native_output, token)
            if (
                result.output_file != native_output
                or result.audio_format != native_format
            ):
                raise ValueError("Preview provider returned an unexpected output.")
            if native_format == "mp3":
                completed = Path(temporary) / "decoded.wav"
                await run_blocking_work(
                    partial(decode_to_wav, native_output, completed), token
                )
            else:
                completed = native_output
            if not self._valid_audio(completed):
                raise ValueError("Preview generation did not produce valid PCM audio.")
            token.raise_if_cancelled()
            os.replace(completed, output)
        self._trim_cache(output)
        return output


class WindowsAudioPlayer:
    """Play one PCM preview asynchronously using Windows' built-in audio API."""

    def play(self, path: Path) -> None:
        """Replace current playback and return immediately while audio plays."""
        import winsound

        winsound.PlaySound(
            str(path),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )

    def stop(self) -> None:
        """Stop playback without waiting for the preview duration."""
        import winsound

        winsound.PlaySound(None, 0)
