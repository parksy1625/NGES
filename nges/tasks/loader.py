"""JSON 벤치마크 태스크 파일 로더 및 검증."""

from __future__ import annotations
import json
from pathlib import Path

# 각 Axis 코드 → 파일명 매핑
TASK_FILES = {
    "A1": "a1_problem_solving.json",
    "A2": "a2_reasoning.json",
    "A3": "a3_memory_recall.json",
    "A4": "a4_consistency.json",
    "A5": "a5_goal_tracking.json",
    "B3": "b3_adaptation.json",
}

# 필수 공통 필드
REQUIRED_FIELDS = {"id", "prompt", "answer_check"}


class TaskLoader:
    """
    tasks/ 디렉터리에서 벤치마크 태스크 JSON을 로드·검증한다.

    load(axis) → list[dict]  태스크 목록 반환
    load_all() → dict        {axis: [tasks]} 전체 반환
    """

    def __init__(self, tasks_path: str = "./tasks"):
        self.path = Path(tasks_path)

    def load(self, axis: str) -> list[dict]:
        """지정 Axis의 태스크 목록을 반환한다."""
        axis = axis.upper()
        filename = TASK_FILES.get(axis)
        if not filename:
            raise ValueError(f"알 수 없는 Axis: '{axis}'. 지원: {list(TASK_FILES.keys())}")

        filepath = self.path / filename
        if not filepath.exists():
            raise FileNotFoundError(f"태스크 파일 없음: {filepath}")

        data = json.loads(filepath.read_text(encoding="utf-8"))
        tasks = data.get("tasks", [])
        self._validate(tasks, axis)
        return tasks

    def load_all(self) -> dict[str, list[dict]]:
        """모든 Axis의 태스크를 로드해서 반환한다."""
        result = {}
        for axis in TASK_FILES:
            try:
                result[axis] = self.load(axis)
            except FileNotFoundError:
                result[axis] = []
        return result

    # ── 검증 ───────────────────────────────────────────────────────────
    @staticmethod
    def _validate(tasks: list[dict], axis: str) -> None:
        if not tasks:
            raise ValueError(f"Axis {axis} 태스크가 비어 있습니다.")

        for i, task in enumerate(tasks):
            # A3, A5는 별도 필드 구조를 허용
            if axis in ("A3",):
                required = {"id", "memory_injection", "recall_prompt", "expected_contains"}
            elif axis == "A5":
                required = {"id", "prompt", "conversation_turns"}
            else:
                required = REQUIRED_FIELDS

            missing = required - task.keys()
            if missing:
                raise ValueError(
                    f"Axis {axis} 태스크[{i}] (id={task.get('id', '?')}) "
                    f"필수 필드 누락: {missing}"
                )
