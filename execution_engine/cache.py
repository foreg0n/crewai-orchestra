# execution_engine/cache.py
import hashlib
import json
import sqlite3
import time
from pathlib import Path


# Типы задач, которые НЕЛЬЗЯ кешировать
# ANALYSIS_TASK — часто содержит запросы о текущих событиях, актуальных данных
NON_CACHEABLE_TYPES = {"ANALYSIS_TASK"}

# Сколько секунд хранить кеш для каждого типа задачи
CACHE_TTL_SECONDS = {
    "SIMPLE_CHAT":   86_400,    # 24 часа — приветствия не меняются
    "SUMMARY_TASK":  21_600,    # 6 часов
    "CODE_TASK":      7_200,    # 2 часа — код быстро устаревает
    "REVIEW_TASK":    3_600,    # 1 час
    "ANALYSIS_TASK":       0,   # не кешируем
}


class RequestCache:
    def __init__(self, db_path: str = "cache.db"):
        # db_path — путь к файлу SQLite. По умолчанию создаётся в корне проекта.
        # check_same_thread=False нужно для FastAPI, который использует несколько потоков
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        """Создаёт таблицу, если её ещё нет."""
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS response_cache (
                key         TEXT PRIMARY KEY,
                task_type   TEXT NOT NULL,
                response    TEXT NOT NULL,
                created_at  REAL NOT NULL,
                ttl         INTEGER NOT NULL,
                hit_count   INTEGER DEFAULT 0
            )
        """)
        self._db.commit()

    def _make_key(self, messages: list[dict], task_type: str) -> str:
        """
        Создаёт хеш-ключ из содержимого запроса.

        Нормализуем текст (lowercase + strip), чтобы "Привет" и "привет"
        давали одинаковый хеш — это главное кейс-нечувствительности.
        """
        payload = {
            "task": task_type,
            "messages": [
                {
                    "role": m.get("role", ""),
                    "content": m.get("content", "").lower().strip(),
                }
                for m in messages
            ],
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def get(self, messages: list[dict], task_type: str) -> dict | None:
        """
        Ищет кешированный ответ.
        Возвращает dict (готовый JSON-ответ) или None если промах.
        """
        if task_type in NON_CACHEABLE_TYPES:
            return None

        key = self._make_key(messages, task_type)
        now = time.time()

        row = self._db.execute(
            "SELECT response, created_at, ttl FROM response_cache WHERE key = ?",
            (key,),
        ).fetchone()

        if not row:
            return None  # промах кеша

        response_json, created_at, ttl = row

        # Проверяем TTL — не истёк ли срок
        if now - created_at > ttl:
            # Запись устарела — удаляем и возвращаем None
            self._db.execute("DELETE FROM response_cache WHERE key = ?", (key,))
            self._db.commit()
            return None

        # Попадание! Обновляем счётчик
        self._db.execute(
            "UPDATE response_cache SET hit_count = hit_count + 1 WHERE key = ?",
            (key,),
        )
        self._db.commit()

        return json.loads(response_json)

    def set(self, messages: list[dict], task_type: str, response: dict):
        """Сохраняет ответ в кеш."""
        ttl = CACHE_TTL_SECONDS.get(task_type, 0)
        if ttl == 0:
            return  # этот тип не кешируем

        key = self._make_key(messages, task_type)
        self._db.execute(
            """
            INSERT OR REPLACE INTO response_cache
                (key, task_type, response, created_at, ttl)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                key,
                task_type,
                json.dumps(response, ensure_ascii=False),
                time.time(),
                ttl,
            ),
        )
        self._db.commit()

    def clear_expired(self):
        """Удаляет устаревшие записи. Вызывать при старте или по расписанию."""
        self._db.execute(
            "DELETE FROM response_cache WHERE (? - created_at) > ttl",
            (time.time(),),
        )
        self._db.commit()

    def stats(self) -> dict:
        """Статистика кеша — видна на /status."""
        rows = self._db.execute(
            "SELECT task_type, COUNT(*), SUM(hit_count) FROM response_cache GROUP BY task_type"
        ).fetchall()
        return {
            row[0]: {"entries": row[1], "total_hits": row[2] or 0}
            for row in rows
        }