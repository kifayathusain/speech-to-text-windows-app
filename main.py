import asyncio
import subprocess
from pathlib import Path

import edge_tts


VOICES = {
    "Receptionist": "en-GB-SoniaNeural",
    "Caller": "en-GB-RyanNeural",
}

INPUT_FILE = "conversation.txt"
OUTPUT_DIR = Path("audio_parts")
FINAL_AUDIO = "conversation.mp3"


async def generate_line(index, speaker, text, voice):
    output_file = OUTPUT_DIR / f"line_{index:03d}.mp3"

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice
    )

    await communicate.save(str(output_file))

    print(f"Created: {output_file}")


async def main():

    OUTPUT_DIR.mkdir(exist_ok=True)

    lines = []

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            speaker, text = line.split(":", 1)

            speaker = speaker.strip()
            text = text.strip()

            if speaker not in VOICES:
                raise ValueError(
                    f"Unknown speaker '{speaker}'. "
                    f"Expected: {list(VOICES.keys())}"
                )

            lines.append(
                (speaker, text, VOICES[speaker])
            )

    # Generate audio files
    for index, (speaker, text, voice) in enumerate(lines, start=1):
        await generate_line(
            index,
            speaker,
            text,
            voice
        )

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
    asyncio.run(main())