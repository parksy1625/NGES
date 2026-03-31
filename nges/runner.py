"""NGES 벤치마크 실행 오케스트레이터."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from .calculator import NGESResult, calculate_nges, assign_grade, calculate_ngi
from .axes import evaluate_axis_a, evaluate_axis_b, evaluate_axis_c

if TYPE_CHECKING:
    from .models.base import AbstractModel
    from .judge.llm_judge import LLMJudge
    from .tasks.loader import TaskLoader
    from .history import HistoryManager


class NGESRunner:
    """
    모든 Axis 평가를 조율하고 NGESResult를 반환한다.

    사용 예::

        runner = NGESRunner(model, judge, task_loader, history_manager)
        result = runner.run(cycle=1)
    """

    def __init__(
        self,
        model: "AbstractModel",
        judge: "LLMJudge",
        task_loader: "TaskLoader",
        history_manager: "HistoryManager",
        baseline_time_ms: float = 3000.0,
        baseline_mem_mb: float  = 150.0,
    ):
        self.model = model
        self.judge = judge
        self.tasks = task_loader
        self.history = history_manager
        self.baseline_time_ms = baseline_time_ms
        self.baseline_mem_mb  = baseline_mem_mb

    # ── 메인 실행 ─────────────────────────────────────────────────────
    def run(self, cycle: int) -> NGESResult:
        timestamp = datetime.now(timezone.utc).isoformat()

        # 태스크 로드
        all_tasks = self.tasks.load_all()

        # 히스토리 로드
        prev_history = self.history.load_previous(self.model.name, cycle)
        all_cycles   = self.history.load_all(self.model.name)

        execution_log: list[dict] = []
        all_responses = []

        # ── Axis A ────────────────────────────────────────────────────
        a_result = self._safe_run_axis(
            "AxisA",
            lambda: evaluate_axis_a(self.model, all_tasks, self.judge, all_responses),
            execution_log,
            default={"a1": 0, "a2": 0, "a3": 0, "a4": 0, "a5": 0, "axis_a": 0},
        )

        # ── Axis B ────────────────────────────────────────────────────
        b_result = self._safe_run_axis(
            "AxisB",
            lambda: evaluate_axis_b(
                self.model,
                all_tasks,
                self.judge,
                prev_history,
                all_cycles,
                all_responses,
                curr_a1=a_result["a1"],
            ),
            execution_log,
            default={"b1": 0, "b2": 0, "b3": 0, "b4": 0, "b5": 7.5, "axis_b": 7.5},
        )

        # ── Axis C ────────────────────────────────────────────────────
        c_result = self._safe_run_axis(
            "AxisC",
            lambda: evaluate_axis_c(
                all_responses,
                execution_log,
                all_cycles,
                axis_a_total=a_result["axis_a"],
                baseline_time_ms=self.baseline_time_ms,
                baseline_mem_mb=self.baseline_mem_mb,
            ),
            execution_log,
            default={"c1": 17.5, "c2": 35, "c3": 15, "axis_c": 67.5,
                     "avg_response_time_ms": 0, "avg_memory_mb": 0},
        )

        # ── NGES 계산 ─────────────────────────────────────────────────
        nges_total = calculate_nges(
            a_result["axis_a"], b_result["axis_b"], c_result["axis_c"]
        )
        grade = assign_grade(nges_total)
        ngi: Optional[float] = None
        if prev_history:
            ngi = calculate_ngi(nges_total, prev_history.get("nges_total", 0.0), 1)

        result = NGESResult(
            # Axis A
            a1=a_result["a1"], a2=a_result["a2"], a3=a_result["a3"],
            a4=a_result["a4"], a5=a_result["a5"],
            # Axis B
            b1=b_result["b1"], b2=b_result["b2"], b3=b_result["b3"],
            b4=b_result["b4"], b5=b_result["b5"],
            # Axis C
            c1=c_result["c1"], c2=c_result["c2"], c3=c_result["c3"],
            # 합산
            axis_a=a_result["axis_a"],
            axis_b=b_result["axis_b"],
            axis_c=c_result["axis_c"],
            # 최종
            nges_total=nges_total,
            grade=grade,
            ngi=ngi,
            # 메타
            model_name=self.model.name,
            cycle=cycle,
            timestamp=timestamp,
            execution_log=execution_log,
            avg_response_time_ms=c_result.get("avg_response_time_ms", 0.0),
            avg_memory_mb=c_result.get("avg_memory_mb", 0.0),
        )

        # 저장
        self.history.save(result)
        return result

    # ── 안전 실행 래퍼 ────────────────────────────────────────────────
    @staticmethod
    def _safe_run_axis(
        module_name: str,
        fn,
        execution_log: list[dict],
        default: dict,
    ) -> dict:
        """
        fn() 실행 중 예외가 발생하면 default를 반환하고 로그에 기록한다.
        C2 모듈 협업 효율 계산에 사용된다.
        """
        try:
            result = fn()
            execution_log.append({"module": module_name, "status": "success"})
            return result
        except Exception as e:
            execution_log.append({
                "module": module_name,
                "status": "error",
                "error_msg": str(e),
            })
            return default
