import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum


class KeyStatus(Enum):
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"
    DEAD = "DEAD"


@dataclass
class KeyState:
    key: str
    provider: str
    status: KeyStatus = KeyStatus.ACTIVE
    requests_today: int = 0
    tokens_today: int = 0
    requests_this_minute: int = 0
    tokens_this_minute: int = 0
    errors: int = 0
    last_used: float = 0.0
    cooldown_until: float = 0.0
    minute_window_start: float = field(default_factory=time.time)

    def reset_minute_window(self):
        now = time.time()
        if now - self.minute_window_start >= 60:
            self.requests_this_minute = 0
            self.tokens_this_minute = 0
            self.minute_window_start = now


class Storage:
    def __init__(self):
        self._keys: Dict[str, KeyState] = {}

    def add_key(self, provider: str, key: str):
        key_id = f"{provider}:{key[:8]}"
        self._keys[key_id] = KeyState(key=key, provider=provider)

    def get_all(self, provider: str) -> list[KeyState]:
        return [s for s in self._keys.values() if s.provider == provider]

    def get_active(self, provider: str) -> list[KeyState]:
        now = time.time()
        result = []
        for state in self._keys.values():
            if state.provider != provider:
                continue
            if state.status == KeyStatus.COOLDOWN and now >= state.cooldown_until:
                state.status = KeyStatus.ACTIVE
                print(f"[STORAGE] {provider} key ...{state.key[:8]} вышел из cooldown")
            if state.status == KeyStatus.ACTIVE:
                state.reset_minute_window()
                result.append(state)
        return result

    def all_states(self) -> list[KeyState]:
        return list(self._keys.values())