"""OpenAI GPT 어댑터."""

from __future__ import annotations
import os
import time

import psutil

from .base import AbstractModel, ModelResponse

DEFAULT_MODEL_ID = "gpt-4o"


class OpenAIModel(AbstractModel):
    def __init__(self, model_id: str = DEFAULT_MODEL_ID):
        import openai  # lazy import
        self.client = openai.OpenAI()
        self.model_id = model_id
        self.name = f"openai:{model_id}"
        self._proc = psutil.Process(os.getpid())

    def _measure(self, messages: list[dict], system: str = "") -> ModelResponse:
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        mem_before = self._proc.memory_info().rss / 1024 ** 2
        t0 = time.perf_counter()

        resp = self.client.chat.completions.create(
            model=self.model_id,
            messages=full_messages,
            max_tokens=4096,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        mem_after = self._proc.memory_info().rss / 1024 ** 2

        return ModelResponse(
            content=resp.choices[0].message.content or "",
            input_tokens=resp.usage.prompt_tokens if resp.usage else None,
            output_tokens=resp.usage.completion_tokens if resp.usage else None,
            response_time_ms=elapsed_ms,
            memory_mb=max(0.0, mem_after - mem_before),
        )

    def complete(self, prompt: str, system: str = "") -> ModelResponse:
        return self._measure([{"role": "user", "content": prompt}], system=system)

    def multi_turn(self, messages: list[dict], system: str = "") -> ModelResponse:
        return self._measure(messages, system=system)
