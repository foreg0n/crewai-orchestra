# execution_engine/context.py
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class ExecutionContext:
    # Уникальный ID запроса — для логов, чтобы можно было отследить запрос
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    # Тип задачи: CODE_TASK, ANALYSIS_TASK, SIMPLE_CHAT и т.д.
    # Заполняет Cost Optimizer на этапе 3
    task_type: str = "ANALYSIS_TASK"

    # Язык пользователя: "ru", "en", "pl" и т.д.
    # Заполняет Language Middleware на этапе 4
    language: str = "en"

    # Число от 0.0 до 1.0 — насколько сложный запрос
    # Заполняет Cost Optimizer на этапе 3
    complexity: float = 0.5

    # Провайдер и модель, выбранные Cost Optimizer
    provider: str = "groq"
    model: str = "llama-3.3-70b"

    # Сколько токенов выделено под ответ модели
    # Заполняет BudgetManager на этапе 1
    output_tokens: int = 2048

    # Системный промт, собранный Prompt Builder на этапе 2
    system_prompt: str = ""

    # История диалога ПОСЛЕ обрезки BudgetManager
    # Может быть короче оригинала, если диалог слишком длинный
    trimmed_history: list = field(default_factory=list)

    # Был ли ответ взят из кэша (без обращения к LLM)
    cache_hit: bool = False

    # Время создания контекста — для замера скорости
    started_at: float = field(default_factory=time.time)

    @property
    def elapsed_ms(self) -> float:
        """Сколько миллисекунд прошло с начала запроса."""
        return (time.time() - self.started_at) * 1000