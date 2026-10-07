"""Application/service layer orchestrating parsing, synthesis and combining.

This is the layer a future UI (M02) should call into instead of talking to
the TTS/FFmpeg adapters directly.
"""

from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import audio_combiner, tts_engine
from .config import DEFAULT_FINAL_AUDIO, DEFAULT_INPUT_FILE, DEFAULT_OUTPUT_DIR, VOICES
from .parser import ConversationLine, parse_conversation

ProgressCallback = Optional[Callable[[int, int, ConversationLine], None]]


async def generate_conversation(
    input_file: Path = DEFAULT_INPUT_FILE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    final_audio: Path = DEFAULT_FINAL_AUDIO,
    voices: Dict[str, str] = VOICES,
    on_progress: ProgressCallback = None,
) -> Path:
    """Run the full pipeline: parse -> synthesize each line -> combine audio.

    Returns the path to the final combined audio file.
    """

    output_dir.mkdir(exist_ok=True)

    lines: List[ConversationLine] = parse_conversation(input_file, voices)

    audio_files: List[Path] = []
    total = len(lines)

    for line in lines:
        output_file = tts_engine.line_output_path(output_dir, line.index)
        await tts_engine.synthesize_line(line.text, line.voice, output_file)
        audio_files.append(output_file)

        if on_progress is not None:
            on_progress(line.index, total, line)

    return audio_combiner.combine_audio(audio_files, output_dir, final_audio)
