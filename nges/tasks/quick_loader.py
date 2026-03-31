"""퀵 벤치마크 로더 — 태스크 5개, 약 1분 완료.

전체 33개 태스크 대신 핵심 태스크만 선별해서 빠르게 실행한다.
처음 연결 테스트, CI 파이프라인, 빠른 회귀 확인에 적합하다.

선별 기준:
  A1: 3개 (정확도 빠른 확인)
  A2: 2개 (추론 품질 확인)
  A3: 생략 (multi-turn 시간 소요)
  A4: 2개, repeat=2 (일관성 빠른 확인)
  A5: 생략 (시나리오 길이 과다)
  B3: 2개 (적응력 확인)
  B4: 2개 (자가 수정 확인)
"""

from __future__ import annotations
from .loader import TaskLoader


class QuickLoader:
    """
    전체 태스크의 약 1/5만 선별하는 빠른 로더.

    TaskLoader와 동일한 인터페이스를 구현해서 Runner에 그대로 전달 가능.
    """

    LIMITS = {
        "A1": 3,
        "A2": 2,
        "A3": 0,   # 생략
        "A4": 2,
        "A5": 0,   # 생략
        "B3": 2,
    }

    def __init__(self, tasks_path: str = "./tasks"):
        self._loader = TaskLoader(tasks_path)

    def load(self, axis: str) -> list[dict]:
        axis = axis.upper()
        limit = self.LIMITS.get(axis, 0)
        if limit == 0:
            return []
        try:
            tasks = self._loader.load(axis)
            return tasks[:limit]
        except (FileNotFoundError, ValueError):
            return []

    def load_all(self) -> dict[str, list[dict]]:
        return {axis: self.load(axis) for axis in self.LIMITS}

    @property
    def quick_repeat(self) -> int:
        """A4 일관성 평가 반복 횟수 (전체: 3회 → 빠른 모드: 2회)."""
        return 2
