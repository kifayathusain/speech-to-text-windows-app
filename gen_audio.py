"""Standalone helper: recombine existing ``audio_parts/line_*.mp3`` segments.

Useful when audio segments already exist (e.g. after a partial/interrupted
run of ``main.py``) and only the final FFmpeg combination step needs to be
re-run. Shares the same FFmpeg adapter as the main pipeline.
"""

from ttsapp.audio_combiner import combine_audio
from ttsapp.config import DEFAULT_FINAL_AUDIO, DEFAULT_OUTPUT_DIR


def main() -> None:
    DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)

    audio_files = sorted(DEFAULT_OUTPUT_DIR.glob("line_*.mp3"))

    if not audio_files:
        raise FileNotFoundError(
            f"No 'line_*.mp3' files found in {DEFAULT_OUTPUT_DIR}/"
        )

    final_audio = combine_audio(audio_files, DEFAULT_OUTPUT_DIR, DEFAULT_FINAL_AUDIO)

    print()
    print(f"Final audio created: {final_audio}")


if __name__ == "__main__":
    main()
