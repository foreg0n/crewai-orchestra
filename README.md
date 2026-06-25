# CrewAI Orchestra + LLM Resource Manager

A multi-agent AI orchestra with automated management of cloud providers,
fallback chains, and API key rotation. Integrates with Odysseus (a self-deployable AI runtime).

## Architecture

```
Odysseus UI
    ↓
CrewAI Orchestra (FastAPI, port 8181)
    ↓
LLM Resource Manager
    ↙        ↓         ↓        ↘
 Groq   OpenRouter  Cerebras  Gemini
```

### Agent Roles

| Role | Provider | Model | Fallback |
|------|-----------|--------|----------|
| CODE_TASK | OpenRouter | Qwen3-Coder-480B | Groq GPT-OSS-120B |
| ANALYSIS_TASK | Cerebras | DeepSeek-R1 | OpenRouter DeepSeek-R1 |
| REVIEW_TASK | Groq | GPT-OSS-120B | Cerebras GPT-OSS-120B |
| SUMMARY_TASK | Cerebras | Llama-3.3-70B | Groq GPT-OSS-20B |
| SIMPLE_CHAT | Cerebras | Llama-3.3-70B | Gemini Flash |

### LRM Features

- Automatic selection of provider and key
- Cooldown after 429 errors with automatic recovery
- Fallback chain—switches to the next provider if a provider is unavailable
- Usage metrics for each provider
- Support for multiple keys from a single provider

## Installation

### 1. Requirements

- Python 3.11
- Docker Desktop (для Odysseus)

### 2. Clone a repository

```bash
git clone https://github.com/YOUR_NAME/crewai-orchestra.git
cd crewai-orchestra
```

### 3. Set up dependencies

```bash
# Windows (Python 3.11)
C:\Users\USERNAME\AppData\Local\Programs\Python\Python311\python.exe -m pip install -r requirements.txt
```

### 4. Configure Keys

```bash
cp .env.example .env
# Open the .env file and paste the API keys
```

Where to pick up the keys:
- **Groq**: https://console.groq.com → API Keys
- **OpenRouter**: https://openrouter.ai → Keys (Top up by $10 for 1,000 requests per day)
- **Cerebras**: https://cloud.cerebras.ai → API Keys
- **Gemini**: https://aistudio.google.com → Get API Key

### 5. Run

```bash
# Windows
start.bat

# Linux / Mac
uvicorn main:app --host 0.0.0.0 --port 8181 --reload
```

### 6. Check

```
http://localhost:8181/health   → {"status": "ok"}
http://localhost:8181/status   → status of all keys and metrics
http://localhost:8181/docs     → Swagger UI
```

## Project Structure

```
crewai-orchestra/
├── main.py                        # FastAPI сервер, CrewAI pipeline
├── router.py                      # Classification of Problems by Type
├── requirements.txt
├── start.bat                      # Running on Windows
├── .env.example                   # Environment Variables Template
├── .gitignore
└── llm_resource_manager/
    ├── __init__.py
    ├── manager.py                 # LRM main class, fallback chains
    ├── scheduler.py               # Choosing a Provider and a Key
    ├── providers.py               # Adapters: Groq, OpenRouter, Cerebras, Gemini
    ├── cooldown.py                # Cooldown Management at 429
    ├── metrics.py                 # Collection of usage metrics
    └── storage.py                 # Key State Storage
```

## Adding a New Provider

1. Add a class to `llm_resource_manager/providers.py`:

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

2. Register with `PROVIDER_CLASSES`:

```python
PROVIDER_CLASSES = {
    ...
    "newprovider": NewProvider,
}
```

3. Add a key to `.env` и `main.py`:

```python
lrm = LLMResourceManager(
    provider_keys={
        ...
        "newprovider": [os.getenv("NEWPROVIDER_API_KEY")],
    }
)
```

4. Add models to fallback chains in `manager.py`.
