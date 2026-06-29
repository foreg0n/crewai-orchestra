# crewai-orchestra

A FastAPI-based LLM orchestration system with a multi-stage **Execution Engine** that optimizes cost, context, and response quality across multiple cloud AI providers.

---

## Architecture

Every request passes through a sequential pipeline before reaching an LLM provider:

```
Request
  │
  ├─► Cache (SQLite)                if HIT → instant response
  │
  ├─► Language Middleware           detect language, build instruction
  │
  ├─► Cost Optimizer                score complexity → select model tier
  │
  ├─► BudgetManager                 trim history to fit context window
  │
  ├─► Dynamic Prompt Builder        assemble system prompt from modules
  │
  └─► LRM → Provider → Response
```

For `expert`-level tasks the request goes through a **CrewAI pipeline** (Analyst → Developer → Reviewer) instead of a single LLM call.

---

## Execution Engine

### Stage 1 — BudgetManager
Counts tokens precisely via `tiktoken` and trims conversation history using a sliding window (newest messages kept first). Allocates token budgets per section based on task type.

### Stage 2 — Dynamic Prompt Builder
Assembles the system prompt on the fly from independent modules (`safety`, `language`, `code`, `analysis`, `summary`, `simple_chat`). No more one giant static prompt — only relevant modules are included per task.

### Stage 3 — Cost Optimizer
Replaces the static regex router. Scores request complexity (0.0–1.0) across five signals: message length, high-complexity keywords, code patterns, trivial/greeting patterns, and conversation depth. Maps the score to the cheapest sufficient model.

| Complexity | Label | Provider | Model |
|---|---|---|---|
| 0.00–0.20 | trivial | Cerebras | Llama 3.3 70B |
| 0.21–0.45 | simple | Gemini | Gemini 2.0 Flash |
| 0.46–0.70 | medium | Groq | GPT-OSS 120B |
| 0.71–0.90 | complex | OpenRouter | DeepSeek R1 |
| 0.91–1.00 | expert | OpenRouter | Qwen3-Coder 480B |

### Stage 4 — Language Middleware
Detects the user's language via `lingua` (with a Cyrillic-ratio fallback). Caches the detected language per session. Injects a language instruction into the system prompt and retries with progressively stronger wording if the model responds in the wrong language (up to 3 attempts).

### Stage 5 — Cache
SHA-256 hashes the normalized request and stores LLM responses in SQLite. Cache is checked first — on a hit, all other stages are skipped entirely. TTL varies by task type; `ANALYSIS_TASK` is never cached.

| Task type | TTL |
|---|---|
| SIMPLE_CHAT | 24 hours |
| SUMMARY_TASK | 6 hours |
| CODE_TASK | 2 hours |
| REVIEW_TASK | 1 hour |
| ANALYSIS_TASK | not cached |

---

## LRM — LLM Resource Manager

Handles provider fallback chains, API key rotation, 429 cooldown management, per-provider metrics, and weighted scheduling.

**Routing table:**

| Task type | Primary | Fallback 1 |
|---|---|---|
| CODE_TASK | OpenRouter Qwen3-Coder | Groq GPT-OSS-120B |
| ANALYSIS_TASK | Cerebras DeepSeek-R1 | OpenRouter DeepSeek-R1 |
| REVIEW_TASK | Groq GPT-OSS-120B | Cerebras GPT-OSS-120B |
| SUMMARY_TASK | Cerebras Llama-3.3-70B | Groq GPT-OSS-20B |
| SIMPLE_CHAT | Cerebras Llama-3.3-70B | Gemini Flash |

---

## Project Structure

```
crewai-orchestra/
├── main.py                        # FastAPI app, request pipeline
├── requirements.txt
├── start.bat                      # Windows quick start
├── .env                           # API keys (not committed)
│
├── execution_engine/
│   ├── __init__.py
│   ├── context.py                 # ExecutionContext dataclass
│   ├── budget_manager.py          # Stage 1 — token budgeting
│   ├── prompt_builder.py          # Stage 2 — dynamic prompt assembly
│   ├── cost_optimizer.py          # Stage 3 — complexity scoring & routing
│   ├── language_middleware.py     # Stage 4 — language detection & retry
│   └── cache.py                   # Stage 5 — SQLite response cache
│
└── llm_resource_manager/
    ├── manager.py                 # LRM core
    ├── scheduler.py               # Provider/key selection
    ├── providers.py               # Groq, OpenRouter, Cerebras, Gemini adapters
    ├── cooldown.py                # 429 cooldown tracking
    ├── metrics.py                 # Per-provider usage metrics
    └── storage.py                 # Key state storage
```

---

## Installation

```bash
git clone https://github.com/foreg0n/crewai-orchestra
cd crewai-orchestra

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root:

```env
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
CEREBRAS_API_KEY=csk-...
GEMINI_API_KEY=AIza...
```

Providers with missing keys are automatically skipped — the system continues with whatever keys are available.

---

## Running

```bash
# Windows
start.bat

# Manual
uvicorn main:app --host 0.0.0.0 --port 8181 --reload
```

---

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/v1/chat/completions` | OpenAI-compatible chat endpoint |
| GET | `/v1/models` | List available models |
| GET | `/health` | Health check |
| GET | `/status` | LRM metrics + cache statistics |

The `/v1/chat/completions` endpoint is fully compatible with the OpenAI API format, so any client that supports OpenAI (Open WebUI, Odysseus, etc.) works out of the box.

**Example request:**

```bash
curl http://localhost:8181/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "привет"}],
    "stream": false
  }'
```

---

## Requirements

- Python 3.11+
- API keys for at least one provider (Groq, OpenRouter, Cerebras, or Gemini)
