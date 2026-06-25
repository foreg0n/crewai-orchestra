import time
import asyncio
from .storage import Storage, KeyStatus
from .cooldown import CooldownManager
from .metrics import MetricsCollector
from .scheduler import Scheduler


# Fallback chains for different task types
FALLBACK_CHAINS = {
    "CODE_TASK": [
        {"provider": "openrouter", "model": "qwen/qwen3-coder"},
        {"provider": "groq",       "model": "gpt-oss-120b"},
        {"provider": "groq",       "model": "llama-3.3-70b-versatile"},
    ],
    "ANALYSIS_TASK": [
        {"provider": "groq",       "model": "llama-3.3-70b-versatile"},
        {"provider": "openrouter", "model": "deepseek/deepseek-r1-0528"},
        {"provider": "groq",       "model": "openai/gpt-oss-20b"},
    ],
    "REVIEW_TASK": [
        {"provider": "groq",       "model": "openai/gpt-oss-120b"},
        {"provider": "cerebras",   "model": "gpt-oss-120b"},
        {"provider": "openrouter", "model": "openai/gpt-oss-120b:free"},
    ],
    "SUMMARY_TASK": [
        {"provider": "groq",       "model": "llama-3.3-70b-versatile"},
        {"provider": "groq",       "model": "openai/gpt-oss-20b"},
        {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b:free"},
    ],
    "SIMPLE_CHAT": [
        {"provider": "groq",       "model": "llama-3.3-70b-versatile"},
        {"provider": "groq",       "model": "openai/gpt-oss-20b"},
        {"provider": "gemini",     "model": "gemini-3-flash"},
    ],
    "ROUTER": [
        {"provider": "openrouter", "model": "openai/gpt-5.4-nano:free"},
        {"provider": "groq",       "model": "openai/gpt-oss-20b"},
    ],
}

MAX_TOKENS = {
    "SIMPLE_CHAT":   256,
    "SUMMARY_TASK":  512,
    "ANALYSIS_TASK": 1024,
    "REVIEW_TASK":   1024,
    "CODE_TASK":     2048,
    "ROUTER":        64,
}


class LLMResourceManager:
    def __init__(self, provider_keys: dict):
        self.storage = Storage()
        self.cooldown = CooldownManager()
        self.metrics = MetricsCollector()
        self.scheduler = Scheduler(self.storage, provider_keys)

    async def chat(self, task_type: str, messages: list,
                   stream: bool = False) -> dict | None:
        chain = FALLBACK_CHAINS.get(task_type, FALLBACK_CHAINS["SIMPLE_CHAT"])
        max_tokens = MAX_TOKENS.get(task_type, 1024)

        for step in chain:
            provider_name = step["provider"]
            model = step["model"]

            result = self.scheduler.pick(provider_name, model)
            if result is None:
                print(f"[LRM] {provider_name} — нет доступных ключей, пропускаю")
                continue

            provider, key_state = result
            start = time.time()

            try:
                print(f"[LRM] {task_type} → {provider_name}/{model}")
                status_code, response = await provider.chat(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    stream=False,
                )

                latency = time.time() - start

                if status_code == 429:
                    reason, retry_after = self.cooldown.parse_retry_after(response)
                    self.cooldown.put_on_cooldown(key_state, reason, retry_after)
                    self.metrics.record(provider_name, 0, latency, error=True)
                    continue

                if status_code >= 500:
                    self.cooldown.put_on_cooldown(key_state, "default", 30)
                    self.metrics.record(provider_name, 0, latency, error=True)
                    continue

                # Успех
                tokens = response.get("usage", {}).get("total_tokens", 500)
                key_state.requests_today += 1
                key_state.tokens_today += tokens
                key_state.requests_this_minute += 1
                key_state.tokens_this_minute += tokens
                key_state.last_used = time.time()
                self.metrics.record(provider_name, tokens, latency)

                print(f"[LRM] ✓ {provider_name} {latency:.1f}с {tokens} токенов")
                return response

            except Exception as e:
                latency = time.time() - start
                print(f"[LRM] ✗ {provider_name} ошибка: {e}")
                self.cooldown.put_on_cooldown(key_state, "default", 30)
                self.metrics.record(provider_name, 0, latency, error=True)
                continue

        print(f"[LRM] ✗ Все провайдеры недоступны для {task_type}")
        return None

    async def stream(self, task_type: str, messages: list):
        chain = FALLBACK_CHAINS.get(task_type, FALLBACK_CHAINS["SIMPLE_CHAT"])
        max_tokens = MAX_TOKENS.get(task_type, 1024)

        for step in chain:
            provider_name = step["provider"]
            model = step["model"]

            result = self.scheduler.pick(provider_name, model)
            if result is None:
                continue

            provider, key_state = result

            try:
                print(f"[LRM] STREAM {task_type} → {provider_name}/{model}")
                async for chunk in provider.stream(model, messages, max_tokens):
                    yield chunk
                key_state.requests_today += 1
                key_state.last_used = time.time()
                return
            except Exception as e:
                print(f"[LRM] STREAM ✗ {provider_name}: {e}")
                self.cooldown.put_on_cooldown(key_state, "default", 30)
                continue

    def get_status(self) -> dict:
        states = self.storage.all_states()
        return {
            "keys": [
                {
                    "provider": s.provider,
                    "key": f"...{s.key[:8]}",
                    "status": s.status.value,
                    "requests_today": s.requests_today,
                    "tokens_today": s.tokens_today,
                    "errors": s.errors,
                }
                for s in states
            ],
            "metrics": self.metrics.get_summary(),
        }