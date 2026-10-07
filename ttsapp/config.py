"""Shared configuration/constants for the TTS application.

Keeping these in one place lets the CLI entry point and a future desktop UI
agree on defaults without duplicating literals.
"""

from pathlib import Path

APP_NAME = "Windows TTS App"
APP_VERSION = "1.0.0"

# Maps a speaker label used in the conversation script to an Edge TTS voice.
VOICES = {
    "Receptionist": "en-GB-SoniaNeural",
    "Caller": "en-GB-RyanNeural",
}

DEFAULT_INPUT_FILE = Path("conversation.txt")
DEFAULT_OUTPUT_DIR = Path("audio_parts")
DEFAULT_FINAL_AUDIO = Path("conversation.mp3")
