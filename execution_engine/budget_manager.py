# execution_engine/budget_manager.py
import tiktoken
from dataclasses import dataclass


# Сколько токенов доступно у каждого провайдера (размер контекстного окна)
PROVIDER_LIMITS = {
    "groq":       32_000,
    "cerebras":    8_192,
    "openrouter": 32_000,
    "gemini":    128_000,
}

# По какому провайдеру будет идти каждый тип задачи (из LRM routing table)
# Нужно, чтобы BudgetManager знал лимит без обращения к LRM
TASK_TO_PROVIDER = {
    "CODE_TASK":     "openrouter",
    "ANALYSIS_TASK": "cerebras",
    "REVIEW_TASK":   "groq",
    "SUMMARY_TASK":  "cerebras",
    "SIMPLE_CHAT":   "cerebras",
}

# Доля бюджета для каждой части промта — разная для разных типов задач
# "output" — это то, сколько мы резервируем под ответ модели
BUDGET_PROFILES = {
    "SIMPLE_CHAT": {
        "system":  0.05,   # 5%  — промт маленький
        "history": 0.05,   # 5%  — история не важна для приветствий
        "user":    0.50,   # 50% — основной запрос
        "output":  0.40,   # 40% резервируем под ответ
    },
    "CODE_TASK": {
        "system":  0.08,
        "history": 0.25,
        "user":    0.30,
        "output":  0.37,
    },
    "ANALYSIS_TASK": {
        "system":  0.05,
        "history": 0.35,   # история важна для анализа — даём больше
        "user":    0.25,
        "output":  0.35,
    },
    "SUMMARY_TASK": {
        "system":  0.05,
        "history": 0.40,   # суммаризация работает с большим контекстом
        "user":    0.20,
        "output":  0.35,
    },
    "REVIEW_TASK": {
        "system":  0.06,
        "history": 0.20,
        "user":    0.40,   # в ревью основное — текущий запрос (код для проверки)
        "output":  0.34,
    },
}

# Дефолтный профиль, если task_type вдруг незнакомый
DEFAULT_PROFILE = BUDGET_PROFILES["ANALYSIS_TASK"]


@dataclass
class BudgetResult:
    output_tokens: int          # сколько токенов отдать под ответ модели
    trimmed_history: list       # история после обрезки
    system_tokens: int          # для логов
    history_tokens: int         # для логов
    user_tokens: int            # для логов


class BudgetManager:
    def __init__(self):
        # cl100k_base — энкодер для GPT-4/ChatGPT, подходит как приближение для всех моделей
        try:
            self._enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._enc = None

    def count_tokens(self, text: str) -> int:
        """Считает токены в тексте. Если tiktoken недоступен — грубая оценка."""
        if self._enc:
            try:
                return len(self._enc.encode(text))
            except Exception:
                pass
        # Фолбек: ~4 символа = 1 токен (работает для латиницы)
        # Для кириллицы ближе к 2-3 символа = 1 токен, ставим 3 как компромисс
        return len(text) // 3

    def apply(
        self,
        messages: list[dict],
        task_type: str,
    ) -> BudgetResult:
        # Определяем провайдера по типу задачи — нужно для лимита
        provider = TASK_TO_PROVIDER.get(task_type, "cerebras")
        total_limit = PROVIDER_LIMITS.get(provider, 8_192)

        profile = BUDGET_PROFILES.get(task_type, DEFAULT_PROFILE)

        # Вычисляем бюджеты в токенах
        hist_budget   = int(total_limit * profile["history"])
        user_budget   = int(total_limit * profile["user"])
        output_budget = int(total_limit * profile["output"])

        # Разделяем messages: последнее user-сообщение + вся остальная история
        user_msgs = [m for m in messages if m.get("role") == "user"]
        last_user = user_msgs[-1]["content"] if user_msgs else ""

        # Всё кроме последнего сообщения — это история
        history = messages[:-1] if messages else []

        # Если user-сообщение слишком длинное — обрезаем его тоже
        user_tokens = self.count_tokens(last_user)
        if user_tokens > user_budget and self._enc:
            tokens = self._enc.encode(last_user)[:user_budget]
            last_user = self._enc.decode(tokens)
            user_tokens = user_budget

        # Sliding window для истории: берём с КОНЦА (последние сообщения важнее)
        # Так сохраняется свежий контекст, а старые сообщения отбрасываются первыми
        trimmed_history = []
        used_hist_tokens = 0

        for msg in reversed(history):
            t = self.count_tokens(msg.get("content", ""))
            if used_hist_tokens + t > hist_budget:
                break  # больше не влезает
            trimmed_history.insert(0, msg)  # вставляем в начало (восстанавливаем порядок)
            used_hist_tokens += t

        return BudgetResult(
            output_tokens=output_budget,
            trimmed_history=trimmed_history,
            system_tokens=0,           # system считается в Prompt Builder
            history_tokens=used_hist_tokens,
            user_tokens=user_tokens,
        )