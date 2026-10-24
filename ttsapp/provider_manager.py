"""Desktop provider selection and session lifecycle without any widget dependency."""

import hashlib
import json
import threading
from dataclasses import asdict, dataclass

from .models.assets import ModelValidationError
from .models.catalog import default_manifest
from .models.kokoro_catalog import kokoro_v1_model
from .models.manager import InstallationState, ModelManager
from .models.piper_catalog import lessac_low_model
from .providers.base import TTSProvider, VoiceMetadata
from .providers.edge import EdgeTTSProvider
from .providers.kokoro import KokoroTTSProvider
from .providers.piper import PiperTTSProvider


@dataclass(frozen=True)
class ProviderChoice:
    """Fast provider/voice metadata suitable for presenting on the UI thread."""

    provider_id: str
    display_name: str
    voices: tuple[VoiceMetadata, ...]
    online: bool
    supports_speed: bool
    model_id: str | None = None


class ProviderManager:
    """Keep one selected provider session and release unused local models."""

    def __init__(self, models: ModelManager | None = None) -> None:
        self.models = models if models is not None else ModelManager()
        self._selected: TTSProvider | None = None
        self._lock = threading.Lock()

    def list_choices(self) -> tuple[ProviderChoice, ...]:
        """Describe choices without opening model files or importing optional runtimes."""
        edge = EdgeTTSProvider()
        kokoro = KokoroTTSProvider(
            kokoro_v1_model(self.models.model_directory("kokoro-82m-v1"))
        )
        piper = PiperTTSProvider(
            (lessac_low_model(self.models.model_directory("piper-lessac-low")),)
        )
        return (
            ProviderChoice(
                "edge", "Microsoft Edge TTS", edge.get_available_voices(), True, False
            ),
            ProviderChoice(
                "kokoro",
                "Kokoro-82M",
                kokoro.get_available_voices(),
                False,
                True,
                "kokoro-82m-v1",
            ),
            ProviderChoice(
                "piper",
                "Piper",
                piper.get_available_voices(),
                False,
                True,
                "piper-lessac-low",
            ),
        )

    def cache_identity(self, provider_id: str) -> str:
        """Include catalog asset versions and digests in preview cache identities."""
        if provider_id == "edge":
            return "edge-adapter-v1"
        if provider_id == "kokoro":
            manifest = default_manifest("kokoro-82m-v1")
        elif provider_id == "piper":
            manifest = default_manifest("piper-lessac-low")
        else:
            raise ValueError(f"Unknown TTS provider: '{provider_id}'.")
        return hashlib.sha256(
            json.dumps(asdict(manifest), sort_keys=True).encode()
        ).hexdigest()

    def get(self, provider_id: str) -> TTSProvider:
        """Resolve a verified model-backed provider; call outside the UI thread."""
        with self._lock:
            if self._selected is not None and self._selected.provider_id == provider_id:
                return self._selected
            if provider_id == "edge":
                provider: TTSProvider = EdgeTTSProvider()
            else:
                if provider_id == "kokoro":
                    model_id = "kokoro-82m-v1"
                elif provider_id == "piper":
                    model_id = "piper-lessac-low"
                else:
                    raise ValueError(f"Unknown TTS provider: '{provider_id}'.")
                if self.models.status(model_id) != InstallationState.INSTALLED:
                    raise ModelValidationError(
                        "Install and verify the selected model in Model library."
                    )
                directory = self.models.model_directory(model_id)
                if provider_id == "kokoro":
                    provider = KokoroTTSProvider(kokoro_v1_model(directory))
                else:
                    provider = PiperTTSProvider((lessac_low_model(directory),))
            if self._selected is not None:
                self._selected.close()
            self._selected = provider
            return provider

    def close(self) -> None:
        """Release the selected model session after any current inference finishes."""
        with self._lock:
            if self._selected is not None:
                self._selected.close()
                self._selected = None
