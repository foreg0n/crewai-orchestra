import time
from .storage import KeyState, Storage
from .providers import BaseProvider, PROVIDER_CLASSES


class Scheduler:
    """
    Selects provider, model, and API key.
    Priority: fewer errors → lower load → longer time since last use.
    """

    def __init__(self, storage: Storage, provider_keys: dict):
        self.storage = storage
        self.provider_keys = provider_keys  # {"groq": ["key1", "key2"], ...}
        self._providers: dict[str, list[BaseProvider]] = {}
        self._build_providers()

    def _build_providers(self):
        for provider, keys in self.provider_keys.items():
            cls = PROVIDER_CLASSES.get(provider)
            if not cls:
                continue
            self._providers[provider] = [cls(k) for k in keys]
            for key in keys:
                self.storage.add_key(provider, key)

    def pick(self, provider: str, model: str) -> tuple[BaseProvider, KeyState] | None:
        """Select the best available key for a provider"""
        active_states = self.storage.get_active(provider)
        if not active_states:
            return None

        # Sort: fewer errors, fewer requests, older last usage first
        active_states.sort(key=lambda s: (s.errors, s.requests_today, -s.last_used))
        best_state = active_states[0]

        # Find provider object matching the key
        for p in self._providers.get(provider, []):
            if p.api_key == best_state.key:
                return p, best_state

        return None

    def get_provider_object(self, provider: str, key: str) -> BaseProvider | None:
        for p in self._providers.get(provider, []):
            if p.api_key == key:
                return p
        return None