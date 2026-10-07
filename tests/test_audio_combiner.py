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


def test_combine_audio_invokes_ffmpeg_with_expected_arguments(tmp_path, monkeypatch):
    audio_files = [tmp_path / "line_001.mp3"]
    audio_files[0].write_bytes(b"fake-audio")
    final_audio = tmp_path / "final.mp3"

    captured_cmd = {}

    def fake_run(cmd, check):
        captured_cmd["cmd"] = cmd
        assert check is True
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(audio_combiner.subprocess, "run", fake_run)

    result = audio_combiner.combine_audio(audio_files, tmp_path, final_audio)

    assert result == final_audio
    cmd = captured_cmd["cmd"]
    assert cmd[0] == "ffmpeg"
    assert str(final_audio) == cmd[-1]
    assert str(tmp_path / "concat.txt") in cmd


def test_combine_audio_raises_clear_error_when_ffmpeg_missing(tmp_path, monkeypatch):
    audio_files = [tmp_path / "line_001.mp3"]
    audio_files[0].write_bytes(b"fake-audio")
    final_audio = tmp_path / "final.mp3"

    def fake_run(cmd, check):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr(audio_combiner.subprocess, "run", fake_run)

    with pytest.raises(audio_combiner.FFmpegNotFoundError):
        audio_combiner.combine_audio(audio_files, tmp_path, final_audio)
