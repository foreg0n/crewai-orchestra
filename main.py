from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from crewai import Agent, Task, Crew, LLM
from dotenv import load_dotenv
from llm_resource_manager import LLMResourceManager
import os, asyncio

load_dotenv()

app = FastAPI()

# Initialization of LRM with all API keys
lrm = LLMResourceManager(
    provider_keys={
        "groq":       [os.getenv("GROQ_API_KEY")],
        "openrouter": [os.getenv("OPENROUTER_API_KEY")],
        "cerebras":   [os.getenv("CEREBRAS_API_KEY")],
        "gemini":     [os.getenv("GEMINI_API_KEY")],
    }
)


def run_crew_pipeline(user_message: str) -> str:
    """CrewAI pipeline for CODE_TASK via cloud providers"""
    analyst = Agent(
        role="Analyst",
        goal="Analyze the task and create a solution plan",
        backstory="Senior analyst with development experience",
        llm=LLM(
            model="qwen/qwen3-coder",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            temperature=0.3,
        ),
        verbose=False,
    )
    coder = Agent(
        role="Developer",
        goal="Write clean working code based on the plan",
        backstory="Senior Python developer",
        llm=LLM(
            model="qwen/qwen3-coder",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            temperature=0.1,
        ),
        verbose=False,
    )
    reviewer = Agent(
        role="Reviewer",
        goal="Find errors and confirm code correctness",
        backstory="Tech Lead focused on code quality",
        llm=LLM(
            model="gpt-oss-120b",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.2,
        ),
        verbose=False,
    )

    result = Crew(
        agents=[analyst, coder, reviewer],
        tasks=[
            Task(
                description=f"Analyze the task: {user_message}",
                expected_output="Structured plan",
                agent=analyst,
            ),
            Task(
                description="Write working Python code based on the plan",
                expected_output="Final code with explanation",
                agent=coder,
            ),
            Task(
                description="Review the code. Finish with tag [APPROVED] or [REVISION NEEDED]",
                expected_output="Final reviewed result",
                agent=reviewer,
            ),
        ],
        verbose=False,
    ).kickoff()
    return str(result)


@app.post("/v1/chat/completions")
async def handle(request: Request):
    from router import classify_task

    body = await request.json()
    messages = body.get("messages", [])
    wants_stream = body.get("stream", False)

    if not messages:
        return JSONResponse({"error": "no messages"}, status_code=400)

    # Clean system context Odysseus
    user_messages = [m for m in messages if m.get("role") == "user"]
    last_msg = user_messages[-1]["content"] if user_messages else messages[-1]["content"]
    if "[Context" in last_msg:
        last_msg = last_msg.split("\n\n")[-1].strip()

    task_type = classify_task(last_msg)
    print(f"\n[ROUTER] '{last_msg[:60]}' → {task_type}")

    # CODE_TASK with long message → CrewAI pipeline
    if task_type == "CODE_TASK" and len(last_msg) > 50:
        print("[ROUTER] → CrewAI pipeline")
        content = await asyncio.to_thread(run_crew_pipeline, last_msg)
        return JSONResponse({
            "id": "crewai-1",
            "object": "chat.completion",
            "choices": [{"index": 0,
                         "message": {"role": "assistant", "content": content},
                         "finish_reason": "stop"}],
            "model": "crewai-orchestra",
            "usage": {"total_tokens": 0},
        })

    # Other tasks → LRM
    if wants_stream:
        return StreamingResponse(
            lrm.stream(task_type, messages),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache",
                     "X-Accel-Buffering": "no"},
        )

    response = await lrm.chat(task_type, messages)
    if response is None:
        return JSONResponse(
            {"error": "all providers are unavailable"},
            status_code=503
        )
    return JSONResponse(response)


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{"id": "orchestra", "object": "model",
                  "created": 0, "owned_by": "local"}],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "crewai-orchestra"}


@app.get("/status")
async def status():
    """Status of all keys and provider metrics"""
    return lrm.get_status()