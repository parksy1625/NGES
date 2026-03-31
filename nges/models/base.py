"""모든 AI 모델 어댑터의 추상 인터페이스."""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelResponse:
    content: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    response_time_ms: float = 0.0   # C1 자원 측정용
    memory_mb: float = 0.0          # C1 자원 측정용


class AbstractModel(ABC):
    """
    모든 모델 어댑터가 구현해야 할 인터페이스.

    name    : 히스토리 파일명 등에 쓰이는 식별자
    complete: 단일 프롬프트 → 응답
    multi_turn: 대화 이력 포함 → 응답 (A3, A5 평가용)
    """

    name: str = "unknown"

    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> ModelResponse:
        """단일 사용자 메시지에 대한 응답을 반환한다."""
        ...

    @abstractmethod
    def multi_turn(self, messages: list[dict], system: str = "") -> ModelResponse:
        """
        대화 이력(messages)을 받아 응답을 반환한다.
        messages 형식: [{"role": "user"/"assistant", "content": "..."}]
        마지막 항목은 반드시 role="user" 여야 한다.
        """
        ...
