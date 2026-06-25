from urllib import response

import httpx
import os
from abc import ABC, abstractmethod


class BaseProvider(ABC):
    name: str
    base_url: str

    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    def get_headers(self) -> dict:
        pass

    async def chat(self, model: str, messages: list,
                   max_tokens: int = 1024, temperature: float = 0.2,
                   stream: bool = False) -> dict:
        headers = self.get_headers()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
        return resp.status_code, resp.json()

    async def stream(self, model: str, messages: list,
                     max_tokens: int = 1024, temperature: float = 0.2):
        headers = {**self.get_headers(), "Accept": "text/event-stream"}
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                print("connected")
                print(resp.status_code)
                print(resp.headers)
                print(await resp.aread())
                async for line in resp.aiter_lines():
                    if line:
                        yield (line + "\n\n").encode("utf-8")


class GroqProvider(BaseProvider):
    name = "groq"
    base_url = "https://api.groq.com/openai/v1"

    def get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }


class OpenRouterProvider(BaseProvider):
    name = "openrouter"
    base_url = "https://openrouter.ai/api/v1"

    def get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://localhost",
            "X-Title": "CrewAI Orchestra",
        }


class CerebrasProvider(BaseProvider):
    name = "cerebras"
    base_url = "https://api.cerebras.ai/v1"

    def get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }


class GeminiProvider(BaseProvider):
    name = "gemini"
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai"

    def get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }


PROVIDER_CLASSES = {
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
    "cerebras": CerebrasProvider,
    "gemini": GeminiProvider,
}