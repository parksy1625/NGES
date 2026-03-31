"""Axis A — 현재 능력 (Current Capability) 평가.

A1: 문제 해결 정확도  (max 30)
A2: 추론 품질         (max 25)
A3: 기억 회수 정확성  (max 20)
A4: 응답 일관성       (max 15)
A5: 장기 목표 유지력  (max 10)
"""

from __future__ import annotations
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.base import AbstractModel, ModelResponse
    from ..judge.llm_judge import LLMJudge


# ── A1: 문제 해결 정확도 ──────────────────────────────────────────────

def evaluate_a1(
    model: "AbstractModel",
    tasks: list[dict],
    judge: "LLMJudge",
    responses_out: list["ModelResponse"] | None = None,
) -> float:
    """
    정답률을 측정한다.
      - answer_check == "exact"     : 응답 전체가 expected_answer와 일치
      - answer_check == "contains"  : 응답에 expected_answer가 포함
      - answer_check == "llm_judge" : Judge 모델로 채점 (0~1 비율)
    """
    if not tasks:
        return 0.0

    correct = 0.0
    for task in tasks:
        resp = model.complete(task["prompt"])
        if responses_out is not None:
            responses_out.append(resp)

        check = task.get("answer_check", "contains")
        expected = task.get("expected_answer", "")

        if check == "exact":
            correct += float(resp.content.strip().lower() == expected.strip().lower())
        elif check == "contains":
            correct += float(expected.lower() in resp.content.lower())
        elif check == "llm_judge":
            rubric = task.get("rubric", "Is the response correct and complete?")
            score, _ = judge.score(task["prompt"], resp.content, rubric, 1.0)
            correct += score

    return (correct / len(tasks)) * 30


# ── A2: 추론 품질 ─────────────────────────────────────────────────────

def evaluate_a2(
    model: "AbstractModel",
    tasks: list[dict],
    judge: "LLMJudge",
    responses_out: list["ModelResponse"] | None = None,
) -> float:
    """LLM Judge로 추론의 깊이와 논리 전개를 평가한다."""
    if not tasks:
        return 0.0

    total = 0.0
    for task in tasks:
        resp = model.complete(task["prompt"])
        if responses_out is not None:
            responses_out.append(resp)

        rubric = task.get(
            "rubric",
            "Does the response show clear step-by-step reasoning? "
            "Are intermediate steps logically sound? Is the conclusion correct?",
        )
        score, _ = judge.score(task["prompt"], resp.content, rubric, 1.0)
        total += score

    return (total / len(tasks)) * 25


# ── A3: 기억 회수 정확성 ──────────────────────────────────────────────

def evaluate_a3(
    model: "AbstractModel",
    tasks: list[dict],
    judge: "LLMJudge",
    responses_out: list["ModelResponse"] | None = None,
) -> float:
    """
    정보를 주입(memory_injection)한 후 delay_turns 만큼 무관한 대화를
    삽입하고, recall_prompt로 기억 회수를 테스트한다.
    """
    if not tasks:
        return 0.0

    correct = 0.0
    for task in tasks:
        messages: list[dict] = [
            {"role": "user",      "content": task["memory_injection"]},
            {"role": "assistant", "content": "Understood. I will remember that."},
        ]

        # 방해 턴 삽입
        for i in range(task.get("delay_turns", 2)):
            messages += [
                {"role": "user",      "content": f"What is {i + 2} + {i + 3}?"},
                {"role": "assistant", "content": str((i + 2) + (i + 3))},
            ]

        messages.append({"role": "user", "content": task["recall_prompt"]})
        resp = model.multi_turn(messages)
        if responses_out is not None:
            responses_out.append(resp)

        expected = task.get("expected_contains", "")
        correct += float(expected.lower() in resp.content.lower())

    return (correct / len(tasks)) * 20


# ── A4: 응답 일관성 ───────────────────────────────────────────────────

def evaluate_a4(
    model: "AbstractModel",
    tasks: list[dict],
    judge: "LLMJudge",
    responses_out: list["ModelResponse"] | None = None,
    repeat: int = 3,
) -> float:
    """
    동일 프롬프트를 repeat 회 반복해서 응답 쌍의 평균 유사도를 계산한다.
    유사도는 SequenceMatcher ratio(0~1)를 사용한다.
    """
    if not tasks:
        return 0.0

    total_similarity = 0.0
    for task in tasks:
        texts = []
        for _ in range(repeat):
            resp = model.complete(task["prompt"])
            if responses_out is not None:
                responses_out.append(resp)
            texts.append(resp.content.strip())

        # 모든 쌍의 유사도 평균
        pairs = [
            (texts[i], texts[j])
            for i in range(len(texts))
            for j in range(i + 1, len(texts))
        ]
        if pairs:
            similarity = sum(
                SequenceMatcher(None, a, b).ratio() for a, b in pairs
            ) / len(pairs)
        else:
            similarity = 1.0

        total_similarity += similarity

    return (total_similarity / len(tasks)) * 15


# ── A5: 장기 목표 유지력 ──────────────────────────────────────────────

def evaluate_a5(
    model: "AbstractModel",
    tasks: list[dict],
    judge: "LLMJudge",
    responses_out: list["ModelResponse"] | None = None,
) -> float:
    """
    멀티턴 시나리오를 제공한다.
    - goal_statement  : 초기 목표
    - conversation_turns : 방해 대화 목록 [{"role": ..., "content": ...}]
    - final_check     : 마지막에 Judge에게 줄 확인 질문
    - rubric          : 채점 기준

    Judge가 '목표가 끝까지 유지되었는가'를 평가한다.
    """
    if not tasks:
        return 0.0

    total = 0.0
    for task in tasks:
        # 시스템 수준 목표 설정
        goal = task.get("goal_statement", "")
        system = f"Your main goal throughout this conversation: {goal}" if goal else ""

        messages: list[dict] = [
            {"role": "user", "content": task["prompt"]},
        ]

        # 중간 대화 삽입
        for turn in task.get("conversation_turns", []):
            if turn["role"] == "user":
                resp = model.multi_turn(messages + [turn], system=system)
                if responses_out is not None:
                    responses_out.append(resp)
                messages.append(turn)
                messages.append({"role": "assistant", "content": resp.content})
            else:
                messages.append(turn)

        # 최종 점검 응답
        final_prompt = task.get("final_check", "Summarize the current status toward your main goal.")
        messages.append({"role": "user", "content": final_prompt})
        final_resp = model.multi_turn(messages, system=system)
        if responses_out is not None:
            responses_out.append(final_resp)

        rubric = task.get(
            "rubric",
            "Did the model maintain focus on its original goal throughout the conversation?",
        )
        score, _ = judge.score(final_prompt, final_resp.content, rubric, 1.0)
        total += score

    return (total / len(tasks)) * 10


# ── 통합 진입점 ───────────────────────────────────────────────────────

def evaluate_axis_a(
    model: "AbstractModel",
    all_tasks: dict[str, list[dict]],
    judge: "LLMJudge",
    responses_out: list["ModelResponse"] | None = None,
) -> dict[str, float]:
    """
    A1~A5를 모두 실행하고 {'a1': ..., ..., 'axis_a': ...} dict를 반환한다.
    responses_out 이 주어지면 모든 ModelResponse를 append한다.
    """
    out = responses_out if responses_out is not None else []

    a1 = evaluate_a1(model, all_tasks.get("A1", []), judge, out)
    a2 = evaluate_a2(model, all_tasks.get("A2", []), judge, out)
    a3 = evaluate_a3(model, all_tasks.get("A3", []), judge, out)
    a4 = evaluate_a4(model, all_tasks.get("A4", []), judge, out)
    a5 = evaluate_a5(model, all_tasks.get("A5", []), judge, out)

    return {
        "a1": a1, "a2": a2, "a3": a3, "a4": a4, "a5": a5,
        "axis_a": a1 + a2 + a3 + a4 + a5,
    }
