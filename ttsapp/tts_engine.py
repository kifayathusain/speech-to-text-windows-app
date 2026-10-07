"""Microsoft Edge TTS adapter.

Isolated so the service layer (and, later, a desktop UI) does not depend
directly on the ``edge_tts`` package or its API shape.
"""

import os
import tempfile
from pathlib import Path

import edge_tts


class TTSGenerationError(RuntimeError):
    """Raised when Edge TTS cannot produce a complete audio file."""


def line_output_path(output_dir: Path, index: int) -> Path:
    """Return the deterministic output path for a given line index."""

    return output_dir / f"line_{index:03d}.mp3"


async def synthesize_line(text: str, voice: str, output_file: Path) -> Path:
    """Synthesize ``text`` with ``voice`` and atomically save it to ``output_file``.

    Edge TTS writes to a temporary file in the destination directory first.
    This keeps failed or cancelled synthesis from leaving a partial output,
    and makes the final replacement atomic on the same filesystem.
    """

    if not text or not text.strip():
        raise ValueError("Speech text cannot be empty.")
    if not voice or not voice.strip():
        raise ValueError("An Edge TTS voice must be selected.")

    temporary_file = None
    temporary_path = None
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_file = tempfile.mkstemp(
            prefix=f".{output_file.stem}.",
            suffix=output_file.suffix or ".mp3",
            dir=str(output_file.parent),
        )
        temporary_path = Path(temporary_file)
        os.close(descriptor)

        communicate = edge_tts.Communicate(text=text, voice=voice)
        await communicate.save(str(temporary_path))

        if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
            raise TTSGenerationError("Edge TTS returned an empty audio file.")

        os.replace(temporary_path, output_file)
        return output_file
    except TTSGenerationError:
        raise
    except Exception as error:
        raise TTSGenerationError(
            f"Edge TTS could not generate audio using voice '{voice}': {error}"
        ) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
