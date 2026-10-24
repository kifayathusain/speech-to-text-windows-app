"""Explicit provider registration without importing optional inference engines."""

from .base import TTSProvider


class ProviderRegistry:
    """Resolve providers by stable ID and reject ambiguous registrations."""

    def __init__(self) -> None:
        self._providers: dict[str, TTSProvider] = {}

    def register(self, provider: TTSProvider) -> None:
        """Register one provider, rejecting empty or duplicate identifiers."""
        identifier = provider.provider_id
        if not identifier or identifier != identifier.strip():
            raise ValueError("Provider ID must be nonempty without outer whitespace.")
        if identifier in self._providers:
            raise ValueError(f"Provider '{identifier}' is already registered.")
        self._providers[identifier] = provider

    def get(self, provider_id: str) -> TTSProvider:
        """Return a registered provider or report an invalid selection."""
        try:
            return self._providers[provider_id]
        except KeyError as error:
            raise ValueError(f"Unknown TTS provider: '{provider_id}'.") from error

    def list_providers(self) -> tuple[TTSProvider, ...]:
        """Return providers in registration order."""
        return tuple(self._providers.values())


def create_default_registry() -> ProviderRegistry:
    """Register Edge without importing any optional local-model dependencies."""
    from .edge import EdgeTTSProvider

    registry = ProviderRegistry()
    registry.register(EdgeTTSProvider())
    return registry
