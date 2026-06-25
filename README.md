# CrewAI Orchestra + LLM Resource Manager

Мультиагентный AI-оркестр с автоматическим управлением облачными провайдерами,
fallback-цепочками и ротацией API-ключей. Интегрируется с Odysseus (self-hosted AI workspace).

## Архитектура

```
Odysseus UI
    ↓
CrewAI Orchestra (FastAPI, port 8181)
    ↓
LLM Resource Manager
    ↙        ↓         ↓        ↘
 Groq   OpenRouter  Cerebras  Gemini
```

### Роли агентов

| Роль | Провайдер | Модель | Fallback |
|------|-----------|--------|----------|
| CODE_TASK | OpenRouter | Qwen3-Coder-480B | Groq GPT-OSS-120B |
| ANALYSIS_TASK | Cerebras | DeepSeek-R1 | OpenRouter DeepSeek-R1 |
| REVIEW_TASK | Groq | GPT-OSS-120B | Cerebras GPT-OSS-120B |
| SUMMARY_TASK | Cerebras | Llama-3.3-70B | Groq GPT-OSS-20B |
| SIMPLE_CHAT | Cerebras | Llama-3.3-70B | Gemini Flash |

### Возможности LRM

- Автоматический выбор провайдера и ключа
- Cooldown при 429 ошибках с авто-восстановлением
- Fallback chain — при недоступности провайдера переключается на следующий
- Метрики использования по каждому провайдеру
- Поддержка нескольких ключей одного провайдера

## Установка

### 1. Требования

- Python 3.11
- Docker Desktop (для Odysseus)

### 2. Клонировать репозиторий

```bash
git clone https://github.com/ТВО_ИМЯ/crewai-orchestra.git
cd crewai-orchestra
```

### 3. Установить зависимости

```bash
# Windows (Python 3.11)
C:\Users\USERNAME\AppData\Local\Programs\Python\Python311\python.exe -m pip install -r requirements.txt
```

### 4. Настроить ключи

```bash
cp .env.example .env
# Открыть .env и вставить API ключи
```

Где получить ключи:
- **Groq**: https://console.groq.com → API Keys
- **OpenRouter**: https://openrouter.ai → Keys (пополни на $10 для 1000 req/day)
- **Cerebras**: https://cloud.cerebras.ai → API Keys
- **Gemini**: https://aistudio.google.com → Get API Key

### 5. Запустить

```bash
# Windows
start.bat

# Linux / Mac
uvicorn main:app --host 0.0.0.0 --port 8181 --reload
```

### 6. Проверить

```
http://localhost:8181/health   → {"status": "ok"}
http://localhost:8181/status   → статус всех ключей и метрики
http://localhost:8181/docs     → Swagger UI
```

## Подключение к Odysseus

В Odysseus → Settings → Add Provider:

```
Name:     CrewAI Orchestra
Base URL: http://host.docker.internal:8181/v1
API Key:  orchestra
```

Выбирай модель `orchestra` в чате — запросы автоматически маршрутизируются.

## Структура проекта

```
crewai-orchestra/
├── main.py                        # FastAPI сервер, CrewAI pipeline
├── router.py                      # Классификация задач по типу
├── requirements.txt
├── start.bat                      # Запуск на Windows
├── .env.example                   # Шаблон переменных окружения
├── .gitignore
└── llm_resource_manager/
    ├── __init__.py
    ├── manager.py                 # Главный класс LRM, fallback chains
    ├── scheduler.py               # Выбор провайдера и ключа
    ├── providers.py               # Адаптеры: Groq, OpenRouter, Cerebras, Gemini
    ├── cooldown.py                # Управление cooldown при 429
    ├── metrics.py                 # Сбор метрик использования
    └── storage.py                 # Хранение состояния ключей
```

## Добавление нового провайдера

1. Добавить класс в `llm_resource_manager/providers.py`:

```python
class NewProvider(BaseProvider):
    name     = "newprovider"
    base_url = "https://api.newprovider.com/v1"

    def get_headers(self) -> dict:
        return {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
```

2. Зарегистрировать в `PROVIDER_CLASSES`:

```python
PROVIDER_CLASSES = {
    ...
    "newprovider": NewProvider,
}
```

3. Добавить ключ в `.env` и `main.py`:

```python
lrm = LLMResourceManager(
    provider_keys={
        ...
        "newprovider": [os.getenv("NEWPROVIDER_API_KEY")],
    }
)
```

4. Добавить модели в fallback chains в `manager.py`.

## Лицензия

MIT
