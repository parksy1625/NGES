"""NGES 점수 계산 엔진"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional

GRADE_TABLE = [
    (90, "S"),
    (75, "A"),
    (60, "B"),
    (45, "C"),
    (30, "D"),
    (0,  "F"),
]

AXIS_WEIGHTS = {
    "A": 0.35,
    "B": 0.45,
    "C": 0.20,
}

# B축 개선율 → 점수 비율 테이블 (threshold %, ratio)
IMPROVEMENT_THRESHOLDS = [
    (15, 1.0),
    (10, 0.8),
    (5,  0.6),
    (1,  0.3),
    (0,  0.0),
]


@dataclass
class NGESResult:
    # ── Axis A 세부 점수 ──────────────────────────────
    a1: float = 0.0   # 문제 해결 정확도   (max 30)
    a2: float = 0.0   # 추론 품질          (max 25)
    a3: float = 0.0   # 기억 회수 정확성   (max 20)
    a4: float = 0.0   # 응답 일관성        (max 15)
    a5: float = 0.0   # 장기 목표 유지력   (max 10)

    # ── Axis B 세부 점수 ──────────────────────────────
    b1: float = 0.0   # 개선 속도          (max 25)
    b2: float = 0.0   # 피드백 반응성      (max 20)
    b3: float = 0.0   # 새 환경 적응력     (max 20)
    b4: float = 0.0   # 자가 수정 효과     (max 20)
    b5: float = 0.0   # 성장 누적성        (max 15)

    # ── Axis C 세부 점수 ──────────────────────────────
    c1: float = 0.0   # 자원 대비 성능     (max 35)
    c2: float = 0.0   # 모듈 협업 효율     (max 35)
    c3: float = 0.0   # 복잡도 안정성      (max 30)

    # ── 축별 합산 (0~100) ─────────────────────────────
    axis_a: float = 0.0
    axis_b: float = 0.0
    axis_c: float = 0.0

    # ── 최종 결과 ─────────────────────────────────────
    nges_total: float = 0.0
    grade: str = "F"
    ngi: Optional[float] = None   # 첫 사이클은 None

    # ── 메타데이터 ────────────────────────────────────
    model_name: str = ""
    cycle: int = 1
    timestamp: str = ""
    execution_log: list = field(default_factory=list)

    # 자원 통계 (C1 참고용)
    avg_response_time_ms: float = 0.0
    avg_memory_mb: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_nges(axis_a: float, axis_b: float, axis_c: float) -> float:
    """세 축을 가중 합산하여 NGES 총점(0~100) 반환."""
    return (
        axis_a * AXIS_WEIGHTS["A"]
        + axis_b * AXIS_WEIGHTS["B"]
        + axis_c * AXIS_WEIGHTS["C"]
    )


def assign_grade(score: float) -> str:
    """NGES 총점을 S~F 등급으로 변환."""
    for threshold, grade in GRADE_TABLE:
        if score >= threshold:
            return grade
    return "F"


def calculate_ngi(current: float, previous: float, cycles: int = 1) -> float:
    """NGI = (현재 NGES - 이전 NGES) / 사이클 수."""
    if cycles <= 0:
        return 0.0
    return (current - previous) / cycles


def improvement_score(prev_score: float, curr_score: float, max_points: float) -> float:
    """
    두 사이클 점수의 개선율(%)을 IMPROVEMENT_THRESHOLDS에 적용해
    0~max_points 범위의 점수를 반환한다.

    prev_score == 0 인 경우:
      - curr_score > 0  → 만점 (첫 성공)
      - curr_score == 0 → 0점
    """
    if prev_score <= 0:
        return max_points if curr_score > 0 else 0.0

    rate = ((curr_score - prev_score) / prev_score) * 100

    for threshold, ratio in IMPROVEMENT_THRESHOLDS:
        if rate >= threshold:
            return max_points * ratio

    return 0.0
