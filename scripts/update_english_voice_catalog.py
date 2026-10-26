"""Rebuild the reviewed Piper English snapshot from an explicit upstream revision.

This developer command uses the network. Application startup never refreshes the
catalog. ONNX SHA-256 values come from upstream LFS metadata; small files are
downloaded and checked against their Git blob identity before hashing.
"""

import argparse
import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

REPOSITORY = "https://huggingface.co/rhasspy/piper-voices"
REVISION = "5041a7a49ae5b3a0f30e6837769eb03fdbb231bd"
OUTPUT = Path("ttsapp/models/piper_english.json")


def read_url(url: str) -> bytes:
    """Fetch one upstream resource with a bounded timeout."""
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def describe_voice(item: tuple[str, dict[str, Any]], revision: str) -> dict[str, Any]:
    """Verify metadata and small assets for one voice model."""
    key, voice = item
    directory = next(iter(voice["files"])).rsplit("/", 1)[0]
    tree = json.loads(
        read_url(
            f"https://huggingface.co/api/models/rhasspy/piper-voices/tree/"
            f"{revision}/{directory}"
        )
    )
    entries = {entry["path"]: entry for entry in tree}
    files = []
    configuration = None
    model_card = None
    for path in voice["files"]:
        entry = entries[path]
        url = f"{REPOSITORY}/resolve/{revision}/{path}"
        if path.endswith(".onnx"):
            digest = entry["lfs"]["oid"]
            size = entry["size"]
        else:
            contents = read_url(url)
            blob = b"blob " + str(len(contents)).encode() + b"\0" + contents
            if hashlib.sha1(blob).hexdigest() != entry["oid"]:
                raise ValueError(f"Git identity mismatch: {path}")
            digest = hashlib.sha256(contents).hexdigest()
            size = len(contents)
            if path.endswith(".onnx.json"):
                configuration = json.loads(contents)
            elif path.endswith("MODEL_CARD"):
                model_card = contents.decode("utf-8")
        files.append(
            dict(
                filename=path.rsplit("/", 1)[-1],
                url=url,
                size_bytes=size,
                sha256=digest,
            )
        )
    if configuration is None or model_card is None:
        raise ValueError(f"Missing configuration or model card: {key}")
    if configuration.get("phoneme_type", "espeak") != "espeak":
        raise ValueError(f"Unsupported phonemizer: {key}")
    count = configuration["num_speakers"]
    speakers = configuration.get("speaker_id_map", {})
    if count > 1 and set(speakers.values()) != set(range(count)):
        raise ValueError(f"Incomplete speaker map: {key}")
    return dict(
        key=key,
        language=voice["language"]["code"].replace("_", "-"),
        quality=voice["quality"],
        num_speakers=count,
        index_num_speakers=voice["num_speakers"],
        speakers=speakers,
        files=files,
        model_card=model_card,
    )


def main() -> None:
    """Write a deterministic snapshot for review; never download model weights."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default=REVISION)
    args = parser.parse_args()
    if len(args.revision) != 40 or any(
        character not in "0123456789abcdef" for character in args.revision
    ):
        parser.error("--revision must be a full lowercase Git commit hash")
    upstream = json.loads(read_url(f"{REPOSITORY}/resolve/{args.revision}/voices.json"))
    selected = sorted(
        (key, voice)
        for key, voice in upstream.items()
        if voice["language"]["code"] in {"en_GB", "en_US"}
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        models = list(
            pool.map(lambda item: describe_voice(item, args.revision), selected)
        )
    snapshot = dict(repository=REPOSITORY, revision=args.revision, models=models)
    OUTPUT.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(models)} English Piper models in {OUTPUT}.")


if __name__ == "__main__":
    main()
