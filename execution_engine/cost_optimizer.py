# execution_engine/cost_optimizer.py
import re
from dataclasses import dataclass

# Ключевые слова, указывающие на сложность
HIGH_COMPLEXITY_PATTERNS = [
    r"(архитектур|спроектируй|разработай систему|сравни \w+ и \w+)",
    r"(оптимизируй|рефактор|проанализируй|объясни принцип)",
    r"(implement|design|architect|compare .+ and .+|optimize)",
]
CODE_PATTERNS = [
    r"(напиши код|write code|function|class|script|sql|bash|dockerfile)",
    r"(```|def |class |import |SELECT |FROM )",
]
SIMPLE_PATTERNS = [
    r"^(привет|hello|hi|ok|ок|спасибо|thanks|да|нет|yes|no)[!?.]*$",
    r"^.{1,30}$",  # очень короткий запрос
]

@dataclass
class RoutingDecision:
    provider: str
    model: str
    complexity: float   # 0.0 – 1.0
    reason: str

# Таблица моделей по уровню сложности
ROUTING_TABLE = [
    # (max_complexity, provider, model, label)
    (0.20, "cerebras",   "llama-3.3-70b",       "trivial"),
    (0.45, "gemini",     "gemini-2.0-flash",     "simple"),
    (0.70, "groq",       "gpt-oss-120b",         "medium"),
    (0.90, "openrouter", "deepseek/deepseek-r1", "complex"),
    (1.00, "openrouter", "qwen/qwen3-coder",     "expert"),
]

class CostOptimizer:
    def score(self, text: str, history: list[dict]) -> float:
        score = 0.0

        # Сигнал 1: длина запроса (нормирована на 1500 символов)
        score += min(len(text) / 1500, 1.0) * 0.25

        # Сигнал 2: паттерны высокой сложности
        text_lower = text.lower()
        if any(re.search(p, text_lower) for p in HIGH_COMPLEXITY_PATTERNS):
            score += 0.35

        # Сигнал 3: паттерны кода
        if any(re.search(p, text_lower) for p in CODE_PATTERNS):
            score += 0.25

        # Сигнал 4: простые приветствия → понижаем до нуля
        if any(re.search(p, text_lower) for p in SIMPLE_PATTERNS):
            score = max(score - 0.50, 0.0)

        # Сигнал 5: глубина истории (длинный диалог → контекст важен)
        score += min(len(history) / 20, 1.0) * 0.15

        return min(score, 1.0)

    def route(self, text: str, history: list[dict]) -> RoutingDecision:
        complexity = self.score(text, history)

        for max_c, provider, model, label in ROUTING_TABLE:
            if complexity <= max_c:
                return RoutingDecision(
                    provider=provider,
                    model=model,
                    complexity=complexity,
                    reason=label,
                )

        # фолбек
        return RoutingDecision("openrouter", "qwen/qwen3-coder", complexity, "fallback")