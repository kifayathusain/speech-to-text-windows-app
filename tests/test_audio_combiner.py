import subprocess
from pathlib import Path

import pytest

from ttsapp import audio_combiner


def test_write_concat_file_lists_files_in_order(tmp_path: Path):
    audio_files = [tmp_path / "line_001.mp3", tmp_path / "line_002.mp3"]
    for file in audio_files:
        file.write_bytes(b"fake-audio")

    concat_file = tmp_path / "concat.txt"
    audio_combiner.write_concat_file(audio_files, concat_file)

    content = concat_file.read_text(encoding="utf-8")
    lines = content.strip().splitlines()

    assert len(lines) == 2
    assert lines[0] == f"file '{audio_files[0].resolve().as_posix()}'"
    assert lines[1] == f"file '{audio_files[1].resolve().as_posix()}'"


def test_write_concat_file_escapes_quotes_in_paths(tmp_path: Path):
    audio_file = tmp_path / "speaker's line.mp3"
    audio_file.write_bytes(b"fake-audio")
    concat_file = tmp_path / "concat.txt"

    audio_combiner.write_concat_file([audio_file], concat_file)

    escaped_path = audio_file.resolve().as_posix().replace("'", "'\\''")
    assert concat_file.read_text(encoding="utf-8") == f"file '{escaped_path}'\n"


def test_combine_audio_invokes_ffmpeg_with_expected_arguments(tmp_path, monkeypatch):
    audio_files = [tmp_path / "line_001.mp3"]
    audio_files[0].write_bytes(b"fake-audio")
    final_audio = tmp_path / "final.mp3"

    captured_cmd = {}

    def fake_run(cmd, check, capture_output, text):
        captured_cmd["cmd"] = cmd
        captured_cmd["concat"] = Path(cmd[cmd.index("-i") + 1]).read_text(
            encoding="utf-8"
        )
        Path(cmd[-1]).write_bytes(b"combined-audio")
        assert check is True
        assert capture_output is True
        assert text is True
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(audio_combiner.subprocess, "run", fake_run)

    result = audio_combiner.combine_audio(audio_files, tmp_path, final_audio)

    assert result == final_audio
    assert final_audio.read_bytes() == b"combined-audio"
    cmd = captured_cmd["cmd"]
    assert cmd[0] == "ffmpeg"
    assert Path(cmd[-1]).parent == final_audio.parent
    assert Path(cmd[-1]).suffix == final_audio.suffix
    assert Path(cmd[-1]) != final_audio
    assert str(tmp_path) in cmd[cmd.index("-i") + 1]
    assert captured_cmd["concat"] == (
        f"file '{audio_files[0].resolve().as_posix()}'\n"
    )
    assert set(tmp_path.iterdir()) == {*audio_files, final_audio}


def test_combine_audio_raises_clear_error_when_ffmpeg_missing(tmp_path, monkeypatch):
    audio_files = [tmp_path / "line_001.mp3"]
    audio_files[0].write_bytes(b"fake-audio")
    final_audio = tmp_path / "final.mp3"

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr(audio_combiner.subprocess, "run", fake_run)

    with pytest.raises(audio_combiner.FFmpegNotFoundError):
        audio_combiner.combine_audio(audio_files, tmp_path, final_audio)

    assert set(tmp_path.iterdir()) == set(audio_files)


def test_combine_audio_reports_ffmpeg_failure_and_preserves_existing_output(
    tmp_path, monkeypatch
):
    audio_file = tmp_path / "line_001.mp3"
    audio_file.write_bytes(b"fake-audio")
    final_audio = tmp_path / "final.mp3"
    final_audio.write_bytes(b"previous-valid-audio")

    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"partial-audio")
        raise subprocess.CalledProcessError(
            1, cmd, stderr="Invalid audio stream"
        )

    monkeypatch.setattr(audio_combiner.subprocess, "run", fake_run)

    with pytest.raises(
        audio_combiner.FFmpegExecutionError, match="Invalid audio stream"
    ):
        audio_combiner.combine_audio([audio_file], tmp_path, final_audio)

    assert final_audio.read_bytes() == b"previous-valid-audio"
    assert set(tmp_path.iterdir()) == {audio_file, final_audio}


def test_combine_audio_rejects_empty_segment_list(tmp_path: Path):
    with pytest.raises(ValueError, match="At least one audio segment"):
        audio_combiner.combine_audio([], tmp_path, tmp_path / "final.mp3")

    assert list(tmp_path.iterdir()) == []


def test_combine_audio_rejects_missing_ffmpeg_output_and_cleans_temporary_files(
    tmp_path, monkeypatch
):
    audio_file = tmp_path / "line_001.mp3"
    audio_file.write_bytes(b"fake-audio")
    final_audio = tmp_path / "final.mp3"

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(audio_combiner.subprocess, "run", fake_run)

    with pytest.raises(audio_combiner.FFmpegExecutionError, match="without producing"):
        audio_combiner.combine_audio([audio_file], tmp_path, final_audio)

    assert not final_audio.exists()
    assert set(tmp_path.iterdir()) == {audio_file}
