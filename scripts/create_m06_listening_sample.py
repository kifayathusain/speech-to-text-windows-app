"""Create a concrete Kokoro chunk/paragraph-join sample for human acceptance."""

import argparse
import asyncio
from pathlib import Path

from ttsapp.models.kokoro_catalog import kokoro_v1_model
from ttsapp.providers.kokoro import KokoroTTSProvider
from ttsapp.service import generate_conversation
from ttsapp.text_processing import TextProcessingSettings

SCRIPT = (
    "Narrator: Dr. Smith checked the notes. The total was $3.14. "
    "We will meet again tomorrow.\n\n"
    "Guest: The next paragraph begins here. Thank you for listening."
)


def main() -> None:
    """Generate the sample and retain its script for reviewing audible joins."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    arguments = parser.parse_args()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    (arguments.output_dir / "script.txt").write_text(SCRIPT, encoding="utf-8")
    provider = KokoroTTSProvider(kokoro_v1_model(arguments.model_dir))
    try:
        output = asyncio.run(
            generate_conversation(
                input_text=SCRIPT,
                voices={"Narrator": "af_heart", "Guest": "bf_emma"},
                provider_id="kokoro",
                provider=provider,
                output_dir=arguments.output_dir / "parts",
                final_audio=arguments.output_dir / "join-review.mp3",
                text_settings=TextProcessingSettings(
                    max_chunk_characters=120,
                    sentence_pause_seconds=0.15,
                    paragraph_pause_seconds=0.4,
                ),
            )
        )
        print(output)
    finally:
        provider.close()


if __name__ == "__main__":
    main()
