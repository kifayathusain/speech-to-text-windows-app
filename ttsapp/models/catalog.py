"""Trusted model manifests; downloading never discovers executable model files."""

import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse


@dataclass(frozen=True)
class DownloadFile:
    """Expected filename, source, size, and SHA-256 for an upstream model asset."""

    filename: str
    url: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.filename):
            raise ValueError("Model filenames must be plain relative file names.")
        source = urlparse(self.url)
        if source.scheme != "https" or source.hostname not in {
            "github.com",
            "huggingface.co",
        }:
            raise ValueError("Model sources must use a trusted upstream HTTPS host.")
        if source.username or source.password:
            raise ValueError("Model source URLs cannot include credentials.")
        if self.size_bytes <= 0:
            raise ValueError("Model asset size must be positive.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("Model assets require a lowercase SHA-256 digest.")


@dataclass(frozen=True)
class ModelManifest:
    """Versioned model metadata, runtime prerequisites, and distribution notices."""

    model_id: str
    version: str
    provider_id: str
    display_name: str
    files: tuple[DownloadFile, ...]
    voices: tuple[str, ...]
    languages: tuple[str, ...]
    license_name: str
    license_url: str
    attribution: str
    runtime: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", self.model_id):
            raise ValueError("Model ID must be a safe directory identifier.")
        if not self.files or len({file.filename for file in self.files}) != len(
            self.files
        ):
            raise ValueError("Model files must be nonempty with unique filenames.")
        if any(file.filename == "installed.json" for file in self.files):
            raise ValueError("Model files cannot use the installation marker filename.")

    @property
    def size_bytes(self) -> int:
        """Total verified download size for the complete model."""
        return sum(file.size_bytes for file in self.files)


@lru_cache(maxsize=1)
def default_catalog() -> tuple[ModelManifest, ...]:
    """Return the quality-first Kokoro catalog and lightweight Piper alternative."""
    from .english_catalog import KOKORO_VOICE_IDS, piper_english_catalog

    kokoro_source = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
    piper_source = (
        "https://huggingface.co/rhasspy/piper-voices/resolve/"
        "5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/en/en_US/lessac/low/"
    )
    return (
        ModelManifest(
            model_id="kokoro-82m-v1",
            version="1.0",
            provider_id="kokoro",
            display_name="Kokoro-82M v1.0 (quality target)",
            files=(
                DownloadFile(
                    "kokoro-v1.0.onnx",
                    kokoro_source + "kokoro-v1.0.onnx",
                    325505369,
                    "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a",
                ),
                DownloadFile(
                    "voices-v1.0.bin",
                    kokoro_source + "voices-v1.0.bin",
                    28214398,
                    "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
                ),
            ),
            voices=KOKORO_VOICE_IDS,
            languages=("en-US", "en-GB"),
            license_name="Apache-2.0 model; see upstream voice/data notices",
            license_url="https://huggingface.co/hexgrad/Kokoro-82M",
            attribution="hexgrad/Kokoro-82M; ONNX export by thewh1teagle; preserve model-card dataset attributions.",
            runtime="Python 3.10–3.13; requirements-kokoro.txt; CPU only",
        ),
        ModelManifest(
            model_id="piper-lessac-low",
            version="1.0.0",
            provider_id="piper",
            display_name="Piper Lessac low (lightweight)",
            files=(
                DownloadFile(
                    "en_US-lessac-low.onnx",
                    piper_source + "en_US-lessac-low.onnx",
                    63201294,
                    "f7d01dde371555732c4c314111ac79672b1a5ce2fc19266ab42178fd8df7f375",
                ),
                DownloadFile(
                    "en_US-lessac-low.onnx.json",
                    piper_source + "en_US-lessac-low.onnx.json",
                    4882,
                    "45754dfdebb3b8661c3fc564713772deec6e064feeb5b4e9594857dc7305193a",
                ),
                DownloadFile(
                    "MODEL_CARD",
                    piper_source + "MODEL_CARD",
                    345,
                    "f4f5b5ab354ab71dd2c71b571bcd0879b259ddfabaa5169b968a60427d0b73f3",
                ),
            ),
            voices=("en_US-lessac-low",),
            languages=("en-US",),
            license_name="Voice: Lessac dataset terms; Piper runtime: GPL-3.0-or-later",
            license_url="https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html",
            attribution="Piper voice from rhasspy/piper-voices; Lessac Blizzard 2013 dataset. See MODEL_CARD.",
            runtime="requirements-piper.txt; CPU only",
        ),
    ) + tuple(
        entry.manifest
        for entry in piper_english_catalog()
        if entry.key != "en_US-lessac-low"
    )


def default_manifest(model_id: str) -> ModelManifest:
    """Resolve a known default manifest for provider descriptors and installers."""
    for manifest in default_catalog():
        if manifest.model_id == model_id:
            return manifest
    raise ValueError(f"Unknown model: '{model_id}'.")
