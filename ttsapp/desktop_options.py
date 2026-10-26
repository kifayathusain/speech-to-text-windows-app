"""Validate desktop controls without depending on Tkinter widgets."""

import math
from dataclasses import dataclass

from .audio_export import ExportSettings, OutputFormat
from .provider_manager import ProviderChoice
from .providers.base import VoiceMetadata
from .text_processing import TextProcessingSettings


def filter_voice_choices(
    choice: ProviderChoice, language: str, query: str
) -> tuple[VoiceMetadata, ...]:
    """Filter names, stable IDs and model identities without accessing weights."""
    terms = query.casefold().split()
    return tuple(
        voice
        for voice in choice.voices
        if (language == "All languages" or voice.language == language)
        and all(
            term in f"{voice.voice_id} {voice.display_name} {voice.model_id}".casefold()
            for term in terms
        )
    )


@dataclass(frozen=True)
class DesktopGenerationOptions:
    """Immutable worker configuration captured on the main UI thread."""

    provider_id: str
    speed: float | None = None
    text_settings: TextProcessingSettings | None = None
    export_settings: ExportSettings | None = None


def build_desktop_options(
    choice: ProviderChoice,
    speed_text: str,
    process_text: bool,
    sentence_pause_text: str,
    paragraph_pause_text: str,
) -> DesktopGenerationOptions:
    """Validate only supported/enabled controls, retaining legacy Edge defaults."""
    speed = None
    if choice.supports_speed:
        try:
            speed = float(speed_text)
        except ValueError as error:
            raise ValueError(
                "Speaking speed must be a number between 0.5 and 2.0."
            ) from error
        if not math.isfinite(speed) or not 0.5 <= speed <= 2.0:
            raise ValueError("Speaking speed must be between 0.5 and 2.0.")
    settings = None
    if process_text or not choice.online:
        try:
            sentence_pause = float(sentence_pause_text)
            paragraph_pause = float(paragraph_pause_text)
        except ValueError as error:
            raise ValueError("Pause durations must be numbers in seconds.") from error
        settings = TextProcessingSettings(
            sentence_pause_seconds=sentence_pause,
            paragraph_pause_seconds=paragraph_pause,
        )
    return DesktopGenerationOptions(choice.provider_id, speed, settings)


def build_export_settings(
    audio_format: str,
    bitrate_text: str,
    sample_rate_text: str,
    channel_text: str,
    normalize: bool,
) -> ExportSettings:
    """Translate explicit desktop choices into validated audio export options."""
    formats: dict[str, OutputFormat] = {"wav": "wav", "mp3": "mp3", "m4a": "m4a"}
    if audio_format not in formats:
        raise ValueError("Export format must be WAV, MP3, or M4A.")
    try:
        bitrate = None
        if audio_format == "mp3" and bitrate_text != "Auto":
            bitrate = int(bitrate_text)
        sample_rate = None if sample_rate_text == "Native" else int(sample_rate_text)
    except ValueError as error:
        raise ValueError(
            "Export bitrate and sample rate must be valid numbers."
        ) from error
    channel_options = {"Source": None, "Mono": 1, "Stereo": 2}
    if channel_text not in channel_options:
        raise ValueError("Select source, mono, or stereo channels.")
    return ExportSettings(
        audio_format=formats[audio_format],
        mp3_bitrate_kbps=bitrate,
        sample_rate=sample_rate,
        channels=channel_options[channel_text],
        normalize=normalize,
    )
