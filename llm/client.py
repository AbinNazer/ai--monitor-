import asyncio
import time
from collections import deque

import httpx
import config
from llm.prompts import SYSTEM_PROMPT, build_user_prompt, build_batch_prompt


class RateLimiter:
    """Sliding-window limiter: max_calls per period (seconds)."""

    def __init__(self, max_calls: int = 35, period: float = 60.0):
        self.max_calls = max_calls
        self.period = period
        self.calls: deque[float] = deque()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            while True:
                now = time.monotonic()
                while self.calls and now - self.calls[0] > self.period:
                    self.calls.popleft()

                if len(self.calls) < self.max_calls:
                    self.calls.append(now)
                    return

                sleep_for = self.period - (now - self.calls[0])
                await asyncio.sleep(max(sleep_for, 0.1))


_limiter = RateLimiter(max_calls=35, period=60.0)  # headroom under the 40/min cap
_concurrency = asyncio.Semaphore(5)  # cap simultaneous in-flight requests too


async def _call_nvidia(messages: list[dict], max_tokens: int = 400, temperature: float = 0.2) -> str:
    await _limiter.acquire()
    async with _concurrency:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{config.NVIDIA_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {config.NVIDIA_API_KEY}"},
                json={
                    "model": config.NVIDIA_MODEL,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()


async def diagnose(alert_text: str, logs: str) -> str:
    """Single-target diagnosis — used when only one breach fires in a poll cycle."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(alert_text, logs)},
    ]
    return await _call_nvidia(messages, max_tokens=300)


async def diagnose_batch(breaches: list[dict], logs_by_target: dict[str, str]) -> str:
    """
    One LLM call covering multiple simultaneous breaches.
    breaches: [{"target": ..., "alert_type": ..., "value": ...}, ...]
    logs_by_target: {target: recent_logs_text}
    Returns one response covering all of them, model is prompted to
    address each target separately and note if they look related.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_batch_prompt(breaches, logs_by_target)},
    ]
    return await _call_nvidia(messages, max_tokens=300 + 150 * len(breaches))


async def ask(question: str, context: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"QUESTION: {question}\n\nCONTEXT:\n{context}"},
    ]
    return await _call_nvidia(messages, max_tokens=400, temperature=0.3)

async def _call_nvidia(messages: list[dict], model: str, max_tokens: int = 400, temperature: float = 0.2) -> str:
    await _limiter.acquire()
    async with _concurrency:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{config.NVIDIA_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {config.NVIDIA_API_KEY}"},
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()

async def diagnose(alert_text: str, logs: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(alert_text, logs)},
    ]
    return await _call_nvidia(messages, model=config.NVIDIA_MODEL_DIAGNOSIS, max_tokens=300)

async def diagnose_batch(breaches: list[dict], logs_by_target: dict[str, str]) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_batch_prompt(breaches, logs_by_target)},
    ]
    return await _call_nvidia(messages, model=config.NVIDIA_MODEL_DIAGNOSIS, max_tokens=300 + 150 * len(breaches))

async def ask(question: str, context: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"QUESTION: {question}\n\nCONTEXT:\n{context}"},
    ]
    return await _call_nvidia(messages, model=config.NVIDIA_MODEL_TOOLCALL, max_tokens=400, temperature=0.3)
