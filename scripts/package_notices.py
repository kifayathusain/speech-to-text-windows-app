"""Retain installed runtime metadata and upstream license files in local builds."""

import argparse
import json
import shutil
import sys
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def write_notices(output: Path, profile: str) -> None:
    """Inventory runtime dependency closure without assigning an application license."""
    pending = ["edge-tts", "pyinstaller"]
    if profile == "full":
        pending.extend(("kokoro-onnx", "piper-tts"))
    records = []
    seen = set()
    while pending:
        name = canonicalize_name(pending.pop())
        if name in seen:
            continue
        seen.add(name)
        distribution = metadata.distribution(name)
        destination = output / "licenses" / name
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "METADATA.txt").write_text(
            distribution.read_text("METADATA") or "", encoding="utf-8"
        )
        copied = []
        for asset in distribution.files or ():
            if ".." in asset.parts:
                continue
            if not any(
                word in asset.name.lower() for word in ("license", "copying", "notice")
            ):
                continue
            source = Path(distribution.locate_file(asset))
            if source.is_file():
                target = destination / str(asset)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied.append(str(asset))
        records.append(
            {
                "name": distribution.metadata["Name"],
                "version": distribution.version,
                "license_expression": distribution.metadata.get("License-Expression"),
                "project_urls": distribution.metadata.get_all("Project-URL", []),
                "license_files": copied,
            }
        )
        for dependency in distribution.requires or ():
            requirement = Requirement(dependency)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise FileNotFoundError("The build runtime must provide Python LICENSE.txt.")
    shutil.copy2(python_license, output / "licenses" / "PYTHON-LICENSE.txt")
    (output / "dependency-inventory.json").write_text(
        json.dumps(sorted(records, key=lambda item: item["name"]), indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "THIRD_PARTY_NOTICES.txt").write_text(
        "Local QA build. See licenses/ and dependency-inventory.json.\n"
        "The full profile includes GPL Piper, phonemizer and eSpeak components.\n"
        "No application license is assigned by the build script. Before public\n"
        "distribution, resolve application-license compatibility and retain\n"
        "complete corresponding source/build materials for GPL components.\n"
        "Model weights are downloaded separately with individual notices.\n",
        encoding="utf-8",
    )


def main() -> None:
    """Generate notices alongside a completed PyInstaller folder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--profile", choices=("full", "edge"), required=True)
    args = parser.parse_args()
    write_notices(args.output, args.profile)


if __name__ == "__main__":
    main()
