# execution_engine/prompt_builder.py
from dataclasses import dataclass, field


@dataclass
class PromptModule:
    name: str
    content: str            # текст модуля, может содержать {placeholders}
    priority: int           # чем выше — тем ближе к началу промта
    task_types: list        # для каких задач включается; пустой список = для всех
    conflicts: list         # имена модулей, которые нельзя включать вместе с этим


# Реестр всех доступных модулей
# Добавить новый модуль = добавить одну запись сюда
MODULE_REGISTRY: dict[str, PromptModule] = {

    "safety": PromptModule(
        name="safety",
        content="You are a helpful assistant. Never produce harmful, illegal, or deceptive content.",
        priority=100,       # всегда первым — главное правило
        task_types=[],      # пустой список = для ВСЕХ типов задач
        conflicts=[],
    ),

    "language": PromptModule(
        name="language",
        content="{language_instruction}",
        priority=90,        # сразу после safety
        task_types=[],
        conflicts=[],
    ),

    "code": PromptModule(
        name="code",
        content=(
            "You are an expert software engineer.\n"
            "Always provide complete, working, production-ready code.\n"
            "Add brief comments for non-obvious logic.\n"
            "If the task is ambiguous, state your assumption before the code."
        ),
        priority=50,
        task_types=["CODE_TASK"],
        conflicts=["simple_chat"],  # не может быть включён вместе с simple_chat
    ),

    "analysis": PromptModule(
        name="analysis",
        content=(
            "You are an analytical assistant.\n"
            "Break complex problems into clear, numbered steps.\n"
            "Support your conclusions with reasoning, not just statements."
        ),
        priority=50,
        task_types=["ANALYSIS_TASK", "REVIEW_TASK"],
        conflicts=[],
    ),

    "summary": PromptModule(
        name="summary",
        content=(
            "You are a summarization assistant.\n"
            "Be concise. Extract only the key points.\n"
            "Use bullet points when listing more than 3 items."
        ),
        priority=50,
        task_types=["SUMMARY_TASK"],
        conflicts=[],
    ),

    "simple_chat": PromptModule(
        name="simple_chat",
        content="Be friendly, brief, and conversational. No need for long explanations.",
        priority=50,
        task_types=["SIMPLE_CHAT"],
        conflicts=["code", "analysis"],
    ),
}


class DynamicPromptBuilder:
    def build(
        self,
        task_type: str,
        language_instruction: str = "",
        memory_context: str = "",
    ) -> str:
        """
        Собирает системный промт из подходящих модулей.

        task_type           — тип задачи (CODE_TASK, SIMPLE_CHAT и т.д.)
        language_instruction — строка вида "Reply in Russian." от LanguageMiddleware
        memory_context      — дополнительный контекст (опционально, для будущего)
        """

        # Шаг 1: отбираем модули, подходящие для данного task_type
        candidates = [
            mod for mod in MODULE_REGISTRY.values()
            if not mod.task_types or task_type in mod.task_types
        ]

        # Шаг 2: разрешаем конфликты — побеждает модуль с большим priority
        active_names: set[str] = set()
        blocked_names: set[str] = set()

        for mod in sorted(candidates, key=lambda m: -m.priority):
            if mod.name in blocked_names:
                continue
            active_names.add(mod.name)
            for conflict in mod.conflicts:
                blocked_names.add(conflict)

        # Шаг 3: оставляем только активные, сортируем по приоритету (высокий → начало)
        active = sorted(
            [m for m in candidates if m.name in active_names],
            key=lambda m: -m.priority,
        )

        # Шаг 4: рендерим каждый модуль (подставляем плейсхолдеры)
        parts = []
        for mod in active:
            rendered = mod.content.format(
                language_instruction=language_instruction or "Reply in English.",
                memory_context=memory_context or "",
            )
            if rendered.strip():
                parts.append(rendered)

        return "\n\n".join(parts)