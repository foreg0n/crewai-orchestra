import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ProviderMetrics:
    provider: str
    total_requests: int = 0
    total_tokens: int = 0
    total_errors: int = 0
    total_latency: float = 0.0
    last_updated: float = field(default_factory=time.time)

    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.total_latency / self.total_requests) * 1000

    def record(self, tokens: int, latency: float, error: bool = False):
        self.total_requests += 1
        self.total_tokens += tokens
        self.total_latency += latency
        if error:
            self.total_errors += 1
        self.last_updated = time.time()


class MetricsCollector:
    def __init__(self):
        self._metrics: Dict[str, ProviderMetrics] = {}

    def record(self, provider: str, tokens: int,
               latency: float, error: bool = False):
        if provider not in self._metrics:
            self._metrics[provider] = ProviderMetrics(provider=provider)
        self._metrics[provider].record(tokens, latency, error)

    def get_summary(self) -> dict:
        return {
            p: {
                "requests": m.total_requests,
                "tokens": m.total_tokens,
                "errors": m.total_errors,
                "avg_latency_ms": round(m.avg_latency_ms, 1),
            }
            for p, m in self._metrics.items()
        }