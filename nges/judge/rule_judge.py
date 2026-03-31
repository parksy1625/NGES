"""Rule-based Judge — API 키 없이 동작하는 채점기.

LLM Judge 대비 정밀도는 낮지만, 외부 API 의존성이 없어
완전 독립 실행이 가능하다.

채점 방식:
  - 응답 길이가 충분한가
  - 명백한 거부/오류 표현이 없는가
  - rubric에 명시된 키워드가 포함되어 있는가
"""

from __future__ import annotations
import re


# 명백한 실패로 간주할 패턴
_FAILURE_PATTERNS = re.compile(
    r"i (don't|cannot|can't|am unable to|do not) (know|answer|help|understand)|"
    r"i'm not sure|"
    r"i have no (idea|information)|"
    r"error|exception|traceback",
    re.IGNORECASE,
)


class RuleBasedJudge:
    """
    API 키 없이 동작하는 규칙 기반 채점기.

    score() 시그니처는 LLMJudge와 동일해서 교체해서 사용 가능.
    """

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
        """
        if not model_response or not model_response.strip():
            return 0.0, "Empty response"

        text = model_response.strip()

        # 명백한 실패 패턴
        if _FAILURE_PATTERNS.search(text):
            return max_score * 0.1, "Response contains failure/uncertainty pattern"

        # 길이 점수 (너무 짧으면 감점)
        length_score = min(1.0, len(text) / 100)

        # rubric 키워드 매칭
        keyword_score = self._keyword_score(text, rubric)

        ratio = (length_score * 0.4) + (keyword_score * 0.6)
        ratio = max(0.0, min(1.0, ratio))

        return ratio * max_score, f"Rule-based: length={length_score:.2f}, keywords={keyword_score:.2f}"

    @staticmethod
    def _keyword_score(text: str, rubric: str) -> float:
        """rubric에서 긍정 키워드를 추출해 응답 포함 여부를 측정."""
        # "Award 1.0 if: ..." 형식에서 키워드 추출
        positive_section = re.split(r"award 0\.|award 0 ", rubric, flags=re.IGNORECASE)[0]

        # 의미있는 단어 추출 (4자 이상, 일반 단어 제외)
        stopwords = {"this", "that", "with", "from", "award", "if", "the",
                     "and", "for", "are", "does", "should", "must", "have",
                     "been", "each", "least", "more", "than", "response",
                     "provides", "provide", "include", "includes", "correct",
                     "correctly", "clear", "clearly"}

        words = re.findall(r"\b[a-zA-Z]{4,}\b", positive_section)
        keywords = [w.lower() for w in words if w.lower() not in stopwords]

        if not keywords:
            return 0.7  # 키워드 추출 실패 시 중간값

        text_lower = text.lower()
        matched = sum(1 for kw in keywords if kw in text_lower)
        return matched / len(keywords)
