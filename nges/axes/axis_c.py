"""Axis C — 구조 효율 (Structural Efficiency) 평가.

C1: 자원 대비 성능  (max 35) — 응답 시간 + 메모리 기반
C2: 모듈 협업 효율  (max 35) — 모듈 실행 성공률
C3: 복잡도 안정성   (max 30) — 사이클 누적 시 성능 안정성
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.base import ModelResponse

# C1 기준값 (config로 덮어쓸 수 있음)
C1_BASELINE_TIME_MS = 3000.0   # 이 값 이하면 시간 점수 만점
C1_BASELINE_MEM_MB  = 150.0    # 이 값 이하면 메모리 점수 만점


# ── C1: 자원 대비 성능 ────────────────────────────────────────────────

def evaluate_c1(
    responses: list["ModelResponse"],
    axis_a_total: float,
    baseline_time_ms: float = C1_BASELINE_TIME_MS,
    baseline_mem_mb: float  = C1_BASELINE_MEM_MB,
) -> tuple[float, float, float]:
    """
    수집된 ModelResponse 목록에서 평균 응답 시간 / 메모리를 계산한다.

    채점 방식:
      - 시간 점수(0~1): baseline 이하이면 1.0, 초과할수록 선형 감소
      - 메모리 점수(0~1): 동일 방식

    Returns:
        (c1_score, avg_time_ms, avg_mem_mb)
    """
    if not responses:
        return 17.5, 0.0, 0.0  # 측정값 없으면 중간값

    avg_time = sum(r.response_time_ms for r in responses) / len(responses)
    avg_mem  = sum(r.memory_mb for r in responses) / len(responses)

    # 시간 점수: baseline의 4배 초과이면 0점
    time_ratio = max(0.0, 1.0 - max(0.0, avg_time - baseline_time_ms) / (baseline_time_ms * 3))
    # 메모리 점수: baseline의 7배 초과이면 0점
    mem_ratio  = max(0.0, 1.0 - max(0.0, avg_mem  - baseline_mem_mb)  / (baseline_mem_mb  * 6))

    # 시간 60%, 메모리 40% 가중
    c1 = (time_ratio * 0.6 + mem_ratio * 0.4) * 35
    return c1, avg_time, avg_mem


# ── C2: 모듈 협업 효율 ───────────────────────────────────────────────

def evaluate_c2(execution_log: list[dict]) -> float:
    """
    실행 로그에서 성공/실패 비율로 채점한다.
    {"module": "A1", "status": "success"/"error", "error_msg": "..."} 형식
    """
    if not execution_log:
        return 35.0  # 실행 로그 없으면 만점 처리 (측정 불가)

    success_count = sum(1 for e in execution_log if e.get("status") == "success")
    rate = success_count / len(execution_log)
    return rate * 35


# ── C3: 복잡도 안정성 ─────────────────────────────────────────────────

def evaluate_c3(all_cycles: list[dict]) -> float:
    """
    사이클이 누적될수록 Axis A 점수의 분산이 낮으면 복잡도 안정성이 높다고 판단.
    사이클 2개 미만이면 중간값 15점 반환.

    채점:
      분산 == 0       → 30점
      분산 < 10       → 25점
      분산 < 25       → 20점
      분산 < 50       → 15점
      분산 < 100      → 10점
      분산 >= 100     →  5점
    """
    if len(all_cycles) < 2:
        return 15.0  # 중간값

    a_scores = [c.get("axis_a", 0.0) for c in all_cycles]
    mean = sum(a_scores) / len(a_scores)
    variance = sum((s - mean) ** 2 for s in a_scores) / len(a_scores)

    if variance == 0:    return 30.0
    if variance < 10:    return 25.0
    if variance < 25:    return 20.0
    if variance < 50:    return 15.0
    if variance < 100:   return 10.0
    return 5.0


# ── 통합 진입점 ───────────────────────────────────────────────────────

def evaluate_axis_c(
    responses: list["ModelResponse"],
    execution_log: list[dict],
    all_cycles: list[dict],
    axis_a_total: float = 0.0,
    baseline_time_ms: float = C1_BASELINE_TIME_MS,
    baseline_mem_mb: float  = C1_BASELINE_MEM_MB,
) -> dict:
    """
    C1~C3를 모두 실행하고
    {'c1': ..., 'c2': ..., 'c3': ..., 'axis_c': ...,
     'avg_response_time_ms': ..., 'avg_memory_mb': ...} dict를 반환한다.
    """
    c1, avg_time, avg_mem = evaluate_c1(responses, axis_a_total, baseline_time_ms, baseline_mem_mb)
    c2 = evaluate_c2(execution_log)
    c3 = evaluate_c3(all_cycles)

    return {
        "c1": c1, "c2": c2, "c3": c3,
        "axis_c": c1 + c2 + c3,
        "avg_response_time_ms": avg_time,
        "avg_memory_mb": avg_mem,
    }
