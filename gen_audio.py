import subprocess
from pathlib import Path


INPUT_FILE = "conversation.txt"
OUTPUT_DIR = Path("audio_parts")
FINAL_AUDIO = "conversation.mp3"

def main():

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Read count from audio parts
    lines = [f for f in OUTPUT_DIR.glob("line_*.mp3")]

    # Create FFmpeg concat file
    concat_file = OUTPUT_DIR / "concat.txt"

    with open(concat_file, "w", encoding="utf-8") as file:

        for index in range(1, len(lines) + 1):
            audio_file = OUTPUT_DIR / f"line_{index:03d}.mp3"

            file.write(
                f"file '{audio_file.resolve().as_posix()}'\n"
            )

    # Combine audio
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            FINAL_AUDIO,
        ],
        check=True,
    )

    print()
    print(f"Final audio created: {FINAL_AUDIO}")


if __name__ == "__main__":
    main()