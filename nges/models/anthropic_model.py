"""Anthropic Claude 어댑터."""

from __future__ import annotations
import os
import time

import psutil

from .base import AbstractModel, ModelResponse

DEFAULT_MODEL_ID = "claude-opus-4-6"


class AnthropicModel(AbstractModel):
    def __init__(self, model_id: str = DEFAULT_MODEL_ID):
        import anthropic  # lazy import — 미설치 시 다른 모델은 동작해야 함
        self.client = anthropic.Anthropic()
        self.model_id = model_id
        self.name = f"anthropic:{model_id}"
        self._proc = psutil.Process(os.getpid())

    # ── 공통 자원 측정 래퍼 ────────────────────────────────────────────
    def _measure(self, fn) -> ModelResponse:
        mem_before = self._proc.memory_info().rss / 1024 ** 2
        t0 = time.perf_counter()

        resp = fn()

        elapsed_ms = (time.perf_counter() - t0) * 1000
        mem_after = self._proc.memory_info().rss / 1024 ** 2

        return ModelResponse(
            content=resp.content[0].text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            response_time_ms=elapsed_ms,
            memory_mb=max(0.0, mem_after - mem_before),
        )

    # ── AbstractModel 구현 ─────────────────────────────────────────────
    def complete(self, prompt: str, system: str = "") -> ModelResponse:
        kwargs = dict(
            model=self.model_id,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        return self._measure(lambda: self.client.messages.create(**kwargs))

    def multi_turn(self, messages: list[dict], system: str = "") -> ModelResponse:
        kwargs = dict(
            model=self.model_id,
            max_tokens=4096,
            messages=messages,
        )
        if system:
            kwargs["system"] = system
        return self._measure(lambda: self.client.messages.create(**kwargs))
