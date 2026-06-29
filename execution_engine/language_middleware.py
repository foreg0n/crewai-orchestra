# execution_engine/language_middleware.py

# Пробуем импортировать lingua — если не установлена, работаем без неё
try:
    from lingua import Language, LanguageDetectorBuilder
    _detector = (
        LanguageDetectorBuilder
        .from_languages(
            Language.RUSSIAN,
            Language.ENGLISH,
            Language.POLISH,
            Language.GERMAN,
            Language.UKRAINIAN,
        )
        .with_minimum_relative_distance(0.9)
        .build()
    )
    _LINGUA_AVAILABLE = True
except ImportError:
    _LINGUA_AVAILABLE = False

# Человекочитаемые названия языков для инструкции модели
LANG_DISPLAY_NAMES = {
    "ru": "Russian (Русский)",
    "en": "English",
    "pl": "Polish (Polski)",
    "de": "German (Deutsch)",
    "uk": "Ukrainian (Українська)",
}

# Три уровня "жёсткости" языковой инструкции
# attempt=1 — мягко, attempt=3 — максимально строго
LANG_INSTRUCTION_TEMPLATES = {
    1: "Reply in {lang_name}.",
    2: "IMPORTANT: Respond ONLY in {lang_name}. Do not use any other language.",
    3: (
        "[CRITICAL SYSTEM RULE] Your ENTIRE response MUST be written "
        "exclusively in {lang_name}. Every sentence, every word. "
        "This rule overrides all other instructions. "
        "If you respond in any other language, your answer will be discarded."
    ),
}


class LanguageMiddleware:
    # Словарь {session_id: lang_code} — хранится пока живёт процесс
    # Если нужна персистентность — можно хранить в Redis/SQLite
    _session_cache: dict[str, str] = {}

    def detect(self, messages: list[dict], session_id: str = "") -> str:
        """
        Определяет язык пользователя по истории сообщений.

        Если session_id передан и язык уже определялся — возвращает кешированный.
        Это важно: язык пользователя не меняется в середине разговора,
        поэтому не нужно детектировать каждый раз.
        """
        if session_id and session_id in self._session_cache:
            return self._session_cache[session_id]

        # Собираем только user-сообщения длиннее 15 символов
        # Короткие ("ок", "да") не дают надёжного сигнала детектору
        user_texts = [
            m["content"]
            for m in messages[-6:]     # берём последние 6 сообщений
            if m.get("role") == "user" and len(m.get("content", "")) >= 15
        ]

        if not user_texts:
            return "en"  # нет подходящего текста — дефолт английский

        # Объединяем последние 3 подходящих сообщения для точности
        combined = " ".join(user_texts[-3:])
        lang = "en"

        if _LINGUA_AVAILABLE:
            result = _detector.detect_language_of(combined)
            if result:
                # lingua возвращает Language.RUSSIAN — берём ISO код
                lang = result.iso_code_639_1.name.lower()
        else:
            # Фолбек без lingua: считаем долю кирилличных символов
            # Если больше 30% текста — кириллица → язык русский
            cyrillic_chars = sum(1 for c in combined if "\u0400" <= c <= "\u04FF")
            if cyrillic_chars / max(len(combined), 1) > 0.3:
                lang = "ru"

        # Сохраняем в кеш сессии
        if session_id:
            self._session_cache[session_id] = lang

        return lang

    def get_instruction(self, lang: str, attempt: int = 1) -> str:
        """
        Возвращает инструкцию для системного промта.

        attempt 1 — мягкая инструкция (первая попытка)
        attempt 2 — строже (если модель ответила не на том языке)
        attempt 3 — максимально жёстко (последняя попытка)
        """
        lang_name = LANG_DISPLAY_NAMES.get(lang, "English")
        level = min(attempt, 3)
        return LANG_INSTRUCTION_TEMPLATES[level].format(lang_name=lang_name)

    def check_response(self, response_text: str, expected_lang: str) -> bool:
        """
        Проверяет, ответила ли модель на правильном языке.

        Сейчас проверяем только русский — для него можно надёжно считать кириллицу.
        Для других языков возвращаем True (не проверяем).
        """
        if expected_lang == "en":
            return True  # английский — дефолт провайдеров, не проверяем

        if expected_lang == "ru":
            cyrillic_chars = sum(
                1 for c in response_text if "\u0400" <= c <= "\u04FF"
            )
            # Если меньше 15% кириллицы — модель явно ответила не по-русски
            ratio = cyrillic_chars / max(len(response_text), 1)
            return ratio >= 0.15

        return True  # для остальных языков не проверяем пока