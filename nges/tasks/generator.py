"""LLM 기반 동적 태스크 생성기.

실행마다 새로운 태스크를 생성해서 정답 암기(벤치마크 오염)를 방지한다.
"""

from __future__ import annotations
import json
import random
import re
import string
import time
from typing import TYPE_CHECKING

from .schemas import AXIS_SCHEMAS, DEFAULT_TASK_COUNTS

if TYPE_CHECKING:
    from ..models.base import AbstractModel


class TaskGenerator:
    """
    LLM을 사용해 실행마다 새로운 벤치마크 태스크를 생성한다.

    generate(axis)     → list[dict]  단일 Axis 태스크 생성
    generate_all()     → dict        전체 Axis 태스크 생성
    """

    def __init__(
        self,
        generator_model: "AbstractModel",
        task_counts: dict[str, int] | None = None,
        max_retries: int = 3,
    ):
        self.model = generator_model
        self.task_counts = task_counts or DEFAULT_TASK_COUNTS
        self.max_retries = max_retries
        self._seed = self._make_seed()

    # ── 공개 인터페이스 ───────────────────────────────────────────────

    def generate(self, axis: str) -> list[dict]:
        """지정 Axis의 태스크를 LLM으로 생성한다."""
        axis = axis.upper()
        schema = AXIS_SCHEMAS.get(axis)
        if not schema:
            raise ValueError(f"알 수 없는 Axis: '{axis}'")

        n = self.task_counts.get(axis, 5)
        prompt = schema["prompt"].format(n=n, seed=self._seed, i="{i}")
        # {i}는 LLM이 채울 자리 → format 후 남아있는 {i}는 그대로 LLM에 전달
        prompt = prompt.replace("{i}", "N")

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.model.complete(prompt, system=schema["system"])
                tasks = self._parse(resp.content, axis)
                self._fix_ids(tasks, axis)
                return tasks
            except Exception as e:
                if attempt == self.max_retries:
                    raise RuntimeError(
                        f"Axis {axis} 태스크 생성 실패 ({self.max_retries}회 시도): {e}"
                    ) from e
                time.sleep(2 ** attempt)  # 지수 백오프

        return []  # unreachable

    def generate_all(self) -> dict[str, list[dict]]:
        """모든 Axis의 태스크를 생성해서 반환한다."""
        result = {}
        for axis in AXIS_SCHEMAS:
            try:
                result[axis] = self.generate(axis)
            except Exception as e:
                print(f"[TaskGenerator] Axis {axis} 생성 실패: {e}")
                result[axis] = []
        return result

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────

    @staticmethod
    def _parse(text: str, axis: str) -> list[dict]:
        """LLM 응답에서 JSON 배열을 추출한다."""
        # 마크다운 코드 펜스 제거
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()

        # JSON 배열 추출
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            raise ValueError(f"Axis {axis}: LLM 응답에서 JSON 배열을 찾을 수 없음\n{text[:300]}")

        tasks = json.loads(match.group())
        if not isinstance(tasks, list):
            raise ValueError(f"Axis {axis}: JSON이 배열이 아님")
        if not tasks:
            raise ValueError(f"Axis {axis}: 빈 태스크 배열")

        return tasks

    def _fix_ids(self, tasks: list[dict], axis: str) -> None:
        """id 필드를 seed 기반으로 고유하게 정규화한다."""
        for i, task in enumerate(tasks):
            task["id"] = f"{axis.lower()}_gen_{self._seed}_{i+1:02d}"
            task["_generated"] = True  # 동적 생성 태스크 마킹

    @staticmethod
    def _make_seed() -> str:
        """실행마다 다른 6자리 랜덤 시드를 생성한다."""
        chars = string.ascii_lowercase + string.digits
        return "".join(random.choices(chars, k=6))

    @property
    def seed(self) -> str:
        return self._seed
