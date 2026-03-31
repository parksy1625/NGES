"""LLM 기반 채점 모듈.

주관적 평가(A2 추론 품질, A5 목표 유지력, B3 적응력 등)를 위해
별도의 Judge 모델이 0.0~1.0 점수를 산출하고 그 근거를 반환한다.
"""

from __future__ import annotations
import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.base import AbstractModel

JUDGE_SYSTEM_PROMPT = """You are a strict, objective AI evaluator for the NGES benchmark.

You will receive:
- TASK: the original question or scenario
- RUBRIC: scoring criteria
- RESPONSE: the model's answer

Your job is to score the response according to the rubric.

Output ONLY a valid JSON object with exactly two keys:
  "score": <float between 0.0 and 1.0>
  "reasoning": "<one concise sentence explaining the score>"

Do not output anything else. Do not include markdown code fences."""


class LLMJudge:
    """
    judge_model을 사용해 model 응답의 품질을 채점한다.

    score() 반환:
      (raw_score, reasoning)
      raw_score 는 0 ~ max_score 범위로 이미 스케일링된 값.
    """

    def __init__(self, judge_model: "AbstractModel"):
        self.model = judge_model

    def score(
        self,
        task_prompt: str,
        model_response: str,
        rubric: str,
        max_score: float = 1.0,
    ) -> tuple[float, str]:
        """
        Returns:
            (scaled_score, reasoning)
            scaled_score: 0.0 ~ max_score
        """
        payload = (
            f"TASK:\n{task_prompt}\n\n"
            f"RUBRIC:\n{rubric}\n\n"
            f"RESPONSE:\n{model_response}"
        )

        try:
            resp = self.model.complete(payload, system=JUDGE_SYSTEM_PROMPT)
            raw = self._parse(resp.content)
            ratio = max(0.0, min(1.0, float(raw["score"])))
            reasoning = str(raw.get("reasoning", ""))
            return ratio * max_score, reasoning
        except Exception as e:
            # Judge 실패 시 보수적으로 0점 반환
            return 0.0, f"[judge error] {e}"

    # ── 파싱 ───────────────────────────────────────────────────────────
    @staticmethod
    def _parse(text: str) -> dict:
        """JSON 블록 추출 및 파싱. 마크다운 펜스 포함 텍스트도 처리."""
        # 마크다운 코드 펜스 제거
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
        # 중괄호 블록만 추출
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Judge 응답에서 JSON을 찾을 수 없음: {text[:200]}")
