"""사이클 결과 영속성 관리."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from .calculator import NGESResult


class HistoryManager:
    """
    결과를 ./history/{model}_cycle{NNNN}.json 형태로 저장·로드한다.
    파일명이 사전순 정렬 가능하도록 cycle을 4자리 0-패딩으로 표기한다.
    """

    def __init__(self, history_path: str = "./history"):
        self.path = Path(history_path)
        self.path.mkdir(parents=True, exist_ok=True)

    # ── 저장 ───────────────────────────────────────────────────────────
    def save(self, result: NGESResult) -> Path:
        filename = self._filename(result.model_name, result.cycle)
        filepath = self.path / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        return filepath

    # ── 단건 로드 ──────────────────────────────────────────────────────
    def load(self, model_name: str, cycle: int) -> Optional[dict]:
        """지정 사이클 결과를 dict로 반환. 없으면 None."""
        filepath = self.path / self._filename(model_name, cycle)
        if not filepath.exists():
            return None
        return json.loads(filepath.read_text(encoding="utf-8"))

    def load_previous(self, model_name: str, cycle: int) -> Optional[dict]:
        """cycle - 1 번째 결과를 반환. 없으면 None."""
        return self.load(model_name, cycle - 1)

    # ── 전체 로드 ──────────────────────────────────────────────────────
    def load_all(self, model_name: str) -> list[dict]:
        """해당 모델의 모든 사이클을 사이클 번호 오름차순으로 반환."""
        pattern = f"{self._safe_name(model_name)}_cycle*.json"
        files = sorted(self.path.glob(pattern))
        results = []
        for f in files:
            try:
                results.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, IOError):
                continue
        return results

    def latest_cycle(self, model_name: str) -> int:
        """저장된 가장 큰 사이클 번호를 반환. 없으면 0."""
        all_cycles = self.load_all(model_name)
        if not all_cycles:
            return 0
        return max(c.get("cycle", 0) for c in all_cycles)

    # ── 내부 헬퍼 ──────────────────────────────────────────────────────
    @staticmethod
    def _safe_name(model_name: str) -> str:
        """파일시스템 안전 이름으로 변환 (슬래시, 콜론 등 제거)."""
        return model_name.replace("/", "_").replace(":", "_").replace(" ", "_")

    def _filename(self, model_name: str, cycle: int) -> str:
        return f"{self._safe_name(model_name)}_cycle{cycle:04d}.json"
