"""Collect CPU phonemization resources, excluding unselected auxiliary models."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("piper")
# Catalog voices use eSpeak. Hebrew/Arabic auxiliary ONNX weights are neither
# selected nor required, and model weights must stay outside the base package.
datas = [item for item in datas if Path(item[0]).suffix not in (".onnx", ".bin")]
