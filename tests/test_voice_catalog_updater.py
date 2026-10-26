"""The developer catalog updater validates upstream identities and speaker maps."""

import hashlib
import json

import pytest

from scripts import update_english_voice_catalog as updater


@pytest.mark.parametrize("corrupt_blob", [False, True])
def test_updater_checks_git_identity_and_uses_configuration_speaker_count(
    monkeypatch: pytest.MonkeyPatch, corrupt_blob: bool
) -> None:
    directory = "en/en_US/test/medium"
    config_name = f"{directory}/en_US-test-medium.onnx.json"
    model_name = f"{directory}/en_US-test-medium.onnx"
    card_name = f"{directory}/MODEL_CARD"
    configuration = json.dumps(
        {
            "num_speakers": 2,
            "speaker_id_map": {"first": 0, "second": 1},
            "phoneme_type": "espeak",
        }
    ).encode()
    card = b"Dataset License: test license"
    contents = {config_name: configuration, card_name: card}
    tree = [{"path": model_name, "size": 42, "lfs": {"oid": "a" * 64}}]
    for path, data in contents.items():
        blob = b"blob " + str(len(data)).encode() + b"\0" + data
        tree.append({"path": path, "oid": hashlib.sha1(blob).hexdigest()})
    if corrupt_blob:
        tree[-1]["oid"] = "0" * 40

    def fetch(url: str) -> bytes:
        if "/tree/" in url:
            return json.dumps(tree).encode()
        for path, data in contents.items():
            if url.endswith(path):
                return data
        pytest.fail(f"Unexpected download (weights must not be fetched): {url}")

    monkeypatch.setattr(updater, "read_url", fetch)
    item = (
        "en_US-test-medium",
        {
            "files": dict.fromkeys([model_name, config_name, card_name]),
            "language": {"code": "en_US"},
            "quality": "medium",
            "num_speakers": 999,
        },
    )
    if corrupt_blob:
        with pytest.raises(ValueError, match="Git identity mismatch"):
            updater.describe_voice(item, updater.REVISION)
    else:
        result = updater.describe_voice(item, updater.REVISION)
        assert result["num_speakers"] == 2
        assert result["index_num_speakers"] == 999
        assert result["files"][0]["sha256"] == "a" * 64
        assert result["files"][1]["sha256"] == hashlib.sha256(configuration).hexdigest()
