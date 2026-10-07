"""Microsoft Edge TTS adapter.

Isolated so the service layer (and, later, a desktop UI) does not depend
directly on the ``edge_tts`` package or its API shape.
"""

from pathlib import Path

import edge_tts


def line_output_path(output_dir: Path, index: int) -> Path:
    """Return the deterministic output path for a given line index."""

    return output_dir / f"line_{index:03d}.mp3"


async def synthesize_line(text: str, voice: str, output_file: Path) -> Path:
    """Synthesize ``text`` with ``voice`` and save it to ``output_file``."""

    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(str(output_file))
    return output_file
