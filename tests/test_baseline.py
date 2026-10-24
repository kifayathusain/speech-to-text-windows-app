"""Regression coverage for original entry points and service boundaries."""

import asyncio
from pathlib import Path

import pytest

import gen_audio
import main as cli
from ttsapp import service, tts_engine


def test_cli_preserves_script_order_voices_and_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise the CLI through real parsing with external adapters replaced."""
    input_file = tmp_path / "conversation.txt"
    input_file.write_text("Caller: Café!\nReceptionist: Welcome.\n", encoding="utf-8")
    output_dir = tmp_path / "parts"
    final_audio = tmp_path / "conversation.mp3"
    synthesized: list[tuple[str, str]] = []

    async def synthesize(text: str, voice: str, output_file: Path) -> Path:
        synthesized.append((text, voice))
        output_file.write_bytes(text.encode("utf-8"))
        return output_file

    def combine(files: list[Path], parts: Path, output: Path) -> Path:
        assert parts == output_dir
        output.write_bytes(b"|".join(file.read_bytes() for file in files))
        return output

    monkeypatch.setattr(cli, "DEFAULT_INPUT_FILE", input_file)
    monkeypatch.setattr(cli, "DEFAULT_OUTPUT_DIR", output_dir)
    monkeypatch.setattr(cli, "DEFAULT_FINAL_AUDIO", final_audio)
    monkeypatch.setattr(tts_engine, "synthesize_line", synthesize)
    monkeypatch.setattr(service.audio_combiner, "combine_audio", combine)

    asyncio.run(cli.main())

    assert synthesized == [
        ("Café!", "en-GB-RyanNeural"),
        ("Welcome.", "en-GB-SoniaNeural"),
    ]
    assert final_audio.read_bytes() == "Café!|Welcome.".encode()
    progress = capsys.readouterr().out
    assert "[1/2] Created: line_001.mp3 (Caller)" in progress
    assert "[2/2] Created: line_002.mp3 (Receptionist)" in progress
    assert str(final_audio) in progress


def test_recombine_helper_orders_existing_segments_and_ignores_other_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the original recovery helper independent of fresh synthesis."""
    output_dir = tmp_path / "parts"
    output_dir.mkdir()
    for name in ["line_002.mp3", "other.mp3", "line_001.mp3"]:
        (output_dir / name).write_bytes(b"audio")
    final_audio = tmp_path / "conversation.mp3"

    def combine(files: list[Path], parts: Path, output: Path) -> Path:
        assert [file.name for file in files] == ["line_001.mp3", "line_002.mp3"]
        assert parts == output_dir
        assert output == final_audio
        output.write_bytes(b"combined")
        return output

    monkeypatch.setattr(gen_audio, "DEFAULT_OUTPUT_DIR", output_dir)
    monkeypatch.setattr(gen_audio, "DEFAULT_FINAL_AUDIO", final_audio)
    monkeypatch.setattr(gen_audio, "combine_audio", combine)

    gen_audio.main()

    assert final_audio.read_bytes() == b"combined"


def test_recombine_helper_rejects_missing_segments_without_replacing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty recovery directory must not overwrite the previous export."""
    final_audio = tmp_path / "conversation.mp3"
    final_audio.write_bytes(b"previous")
    monkeypatch.setattr(gen_audio, "DEFAULT_OUTPUT_DIR", tmp_path / "parts")
    monkeypatch.setattr(gen_audio, "DEFAULT_FINAL_AUDIO", final_audio)

    with pytest.raises(FileNotFoundError, match="No 'line_"):
        gen_audio.main()

    assert final_audio.read_bytes() == b"previous"


def test_service_cancellation_preserves_final_and_skips_combination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation propagates while completed segments remain available."""
    final_audio = tmp_path / "conversation.mp3"
    final_audio.write_bytes(b"previous")
    output_dir = tmp_path / "parts"
    progress: list[int] = []

    async def synthesize(text: str, voice: str, output_file: Path) -> Path:
        if text == "Cancel":
            raise asyncio.CancelledError
        output_file.write_bytes(b"completed")
        return output_file

    def unexpected_combine(*args: object) -> Path:
        pytest.fail("Cancellation must prevent final audio combination")

    monkeypatch.setattr(tts_engine, "synthesize_line", synthesize)
    monkeypatch.setattr(service.audio_combiner, "combine_audio", unexpected_combine)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            service.generate_conversation(
                input_text="Caller: First\nCaller: Cancel\nCaller: Never",
                output_dir=output_dir,
                final_audio=final_audio,
                on_progress=lambda index, total, line: progress.append(index),
            )
        )

    assert progress == [1]
    assert final_audio.read_bytes() == b"previous"
    assert [file.name for file in output_dir.iterdir()] == ["line_001.mp3"]


def test_service_validates_entire_script_before_creating_outputs(
    tmp_path: Path,
) -> None:
    """A malformed later line must fail before any synthesis side effects."""
    output_dir = tmp_path / "parts"

    with pytest.raises(ValueError, match="Malformed line"):
        asyncio.run(
            service.generate_conversation(
                input_text="Caller: Valid\nMissing speaker separator",
                output_dir=output_dir,
                final_audio=tmp_path / "conversation.mp3",
            )
        )

    assert list(tmp_path.iterdir()) == []
