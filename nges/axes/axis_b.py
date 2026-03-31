"""Axis B — 성장 속도 (Growth Velocity) 평가.

B1: 개선 속도        (max 25) — 이전 사이클 A1 대비 향상
B2: 피드백 반응성    (max 20) — 피드백 주입 후 재평가
B3: 새 환경 적응력   (max 20) — 처음 접하는 도메인 적응 속도
B4: 자가 수정 효과   (max 20) — Reflection 루프 전후 비교
B5: 성장 누적성      (max 15) — 히스토리 전체 NGES 추세
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from ..calculator import improvement_score

if TYPE_CHECKING:
    from ..models.base import AbstractModel, ModelResponse
    from ..judge.llm_judge import LLMJudge


# ── B1: 개선 속도 ─────────────────────────────────────────────────────

def evaluate_b1(prev_a1: float, curr_a1: float) -> float:
    """이전 사이클 A1 점수 대비 현재 A1 점수의 개선율로 채점."""
    return improvement_score(prev_a1, curr_a1, 25)


# ── B2: 피드백 반응성 ─────────────────────────────────────────────────

def evaluate_b2(
    model: "AbstractModel",
    tasks: list[dict],
    prev_history: Optional[dict],
    judge: "LLMJudge",
    responses_out: list["ModelResponse"] | None = None,
) -> float:
    """
    이전 사이클의 실패 정보를 시스템 프롬프트로 주입해서 재평가하고,
    이전 A1 점수와 비교해 개선율로 채점한다.
    """
    if not tasks or not prev_history:
        return 0.0

    feedback = _build_feedback_prompt(prev_history)
    system = (
        "You are an AI that learns from past mistakes.\n\n"
        f"Previous evaluation feedback:\n{feedback}\n\n"
        "Apply these lessons to answer the following questions more accurately."
    )

    correct = 0.0
    for task in tasks:
        resp = model.complete(task["prompt"], system=system)
        if responses_out is not None:
            responses_out.append(resp)

        check = task.get("answer_check", "contains")
        expected = task.get("expected_answer", "")

        if check == "exact":
            correct += float(resp.content.strip().lower() == expected.strip().lower())
        elif check == "contains":
            correct += float(expected.lower() in resp.content.lower())
        elif check == "llm_judge":
            rubric = task.get("rubric", "Is the response correct?")
            score, _ = judge.score(task["prompt"], resp.content, rubric, 1.0)
            correct += score

    curr_a1_normalized = (correct / len(tasks)) * 30 if tasks else 0.0
    prev_a1 = prev_history.get("a1", 0.0)
    return improvement_score(prev_a1, curr_a1_normalized, 20)


def _build_feedback_prompt(prev_history: dict) -> str:
    """이전 사이클 결과에서 피드백 텍스트를 생성한다."""
    lines = []
    a1 = prev_history.get("a1", 0)
    a2 = prev_history.get("a2", 0)
    a3 = prev_history.get("a3", 0)
    lines.append(f"- Problem solving accuracy: {a1:.1f}/30")
    lines.append(f"- Reasoning quality: {a2:.1f}/25")
    lines.append(f"- Memory recall: {a3:.1f}/20")

    log = prev_history.get("execution_log", [])
    errors = [e for e in log if e.get("status") == "error"]
    if errors:
        lines.append("- Modules that had errors: " + ", ".join(e["module"] for e in errors))

    return "\n".join(lines) if lines else "No specific feedback available."


# ── B3: 새 환경 적응력 ────────────────────────────────────────────────

def evaluate_b3(
    model: "AbstractModel",
    tasks: list[dict],
    judge: "LLMJudge",
    responses_out: list["ModelResponse"] | None = None,
) -> float:
    """
    처음 접하는 novel 도메인에서의 적응 속도를 측정한다.
    동일 도메인 내 첫 문제 → 두 번째 문제로의 성능 향상 곡선을 사용한다.
    도메인 그룹이 없으면 단순 전체 정확도 기반으로 채점한다.
    """
    if not tasks:
        return 0.0

    # 도메인별 그룹화
    domain_groups: dict[str, list[dict]] = {}
    for task in tasks:
        domain = task.get("domain", "general")
        domain_groups.setdefault(domain, []).append(task)

    total_improvement = 0.0
    domain_count = 0

    for domain, domain_tasks in domain_groups.items():
        if len(domain_tasks) < 2:
            # 단일 태스크: 단순 정확도
            resp = model.complete(domain_tasks[0]["prompt"])
            if responses_out is not None:
                responses_out.append(resp)
            rubric = domain_tasks[0].get("rubric", "Is the response relevant and correct?")
            score, _ = judge.score(domain_tasks[0]["prompt"], resp.content, rubric, 1.0)
            total_improvement += score * 20
            domain_count += 1
            continue

        scores = []
        for task in domain_tasks:
            resp = model.complete(task["prompt"])
            if responses_out is not None:
                responses_out.append(resp)
            rubric = task.get("rubric", "Is the response relevant and correct?")
            s, _ = judge.score(task["prompt"], resp.content, rubric, 1.0)
            scores.append(s)

        # 첫 → 마지막 점수 향상 비율
        first, last = scores[0], scores[-1]
        improvement = improvement_score(first if first > 0 else 0.5, last, 1.0)
        total_improvement += improvement
        domain_count += 1

    if domain_count == 0:
        return 0.0
    return (total_improvement / domain_count) * 20


# ── B4: 자가 수정 효과 ────────────────────────────────────────────────

REFLECTION_TEMPLATE = (
    "You previously answered this question:\n"
    "QUESTION: {question}\n\n"
    "YOUR PREVIOUS ANSWER: {previous_answer}\n\n"
    "Critically reflect on your answer:\n"
    "1. What mistakes or gaps did you make?\n"
    "2. What would a better answer include?\n\n"
    "Now provide a corrected, improved answer."
)


def evaluate_b4(
    model: "AbstractModel",
    tasks: list[dict],
    judge: "LLMJudge",
    responses_out: list["ModelResponse"] | None = None,
) -> float:
    """
    각 태스크에 대해 1차 응답 → Reflection 프롬프트 → 2차 응답 순서로 실행.
    1차 vs 2차 점수의 개선율로 채점한다.
    """
    if not tasks:
        return 0.0

    first_scores = []
    second_scores = []

    for task in tasks:
        rubric = task.get(
            "rubric",
            "Is the response logically sound, accurate, and complete?",
        )

        # 1차 응답
        r1 = model.complete(task["prompt"])
        if responses_out is not None:
            responses_out.append(r1)
        s1, _ = judge.score(task["prompt"], r1.content, rubric, 1.0)

        # Reflection 후 2차 응답
        reflect_prompt = REFLECTION_TEMPLATE.format(
            question=task["prompt"],
            previous_answer=r1.content,
        )
        r2 = model.complete(reflect_prompt)
        if responses_out is not None:
            responses_out.append(r2)
        s2, _ = judge.score(task["prompt"], r2.content, rubric, 1.0)

        first_scores.append(s1)
        second_scores.append(s2)

    avg_before = sum(first_scores) / len(first_scores)
    avg_after  = sum(second_scores) / len(second_scores)
    return improvement_score(avg_before if avg_before > 0 else 0.5, avg_after, 20)


# ── B5: 성장 누적성 ───────────────────────────────────────────────────

def evaluate_b5(all_cycles: list[dict]) -> float:
    """
    모든 사이클의 NGES 총점을 선형 회귀로 분석해 성장 추세를 측정한다.
    사이클이 2개 미만이면 7.5점(중간값)으로 초기화한다.

    slope 기준 (NGES 점 / 사이클):
      >= 2.0  → 15점
      >= 1.0  → 12점
      >= 0.1  →  9점
      >= 0.0  →  5점
       < 0.0  →  0점 (퇴행)
    """
    if len(all_cycles) < 2:
        return 7.5  # 첫 사이클 중간값

    scores = [c.get("nges_total", 0.0) for c in all_cycles]
    n = len(scores)
    x_mean = (n - 1) / 2.0
    y_mean = sum(scores) / n

    denom = sum((i - x_mean) ** 2 for i in range(n))
    if denom == 0:
        slope = 0.0
    else:
        slope = sum((i - x_mean) * (s - y_mean) for i, s in enumerate(scores)) / denom

    if slope >= 2.0:
        return 15.0
    if slope >= 1.0:
        return 12.0
    if slope >= 0.1:
        return 9.0
    if slope >= 0.0:
        return 5.0
    return 0.0


# ── 통합 진입점 ───────────────────────────────────────────────────────

def evaluate_axis_b(
    model: "AbstractModel",
    all_tasks: dict[str, list[dict]],
    judge: "LLMJudge",
    prev_history: Optional[dict],
    all_cycles: list[dict],
    responses_out: list["ModelResponse"] | None = None,
    curr_a1: float = 0.0,
) -> dict[str, float]:
    """
    B1~B5를 모두 실행하고 {'b1': ..., ..., 'axis_b': ...} dict를 반환한다.
    prev_history가 None이면 B1, B2는 0점으로 처리된다.
    """
    out = responses_out if responses_out is not None else []

    # B1: 이전 A1 대비 현재 A1 개선율
    if prev_history:
        b1 = evaluate_b1(prev_history.get("a1", 0.0), curr_a1)
        b2 = evaluate_b2(model, all_tasks.get("A1", []), prev_history, judge, out)
    else:
        b1 = 0.0
        b2 = 0.0

    b3 = evaluate_b3(model, all_tasks.get("B3", []), judge, out)
    b4 = evaluate_b4(model, all_tasks.get("A2", []), judge, out)  # A2 태스크 재사용
    b5 = evaluate_b5(all_cycles)

    return {
        "b1": b1, "b2": b2, "b3": b3, "b4": b4, "b5": b5,
        "axis_b": b1 + b2 + b3 + b4 + b5,
    }
