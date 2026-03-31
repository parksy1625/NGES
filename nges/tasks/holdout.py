"""Hold-out 세트 관리자.

비공개 평가 태스크를 로컬에만 보관하고 git에는 올라가지 않는다.
tasks/holdout/ 디렉터리는 .gitignore에 포함된다.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .generator import TaskGenerator

DEFAULT_HOLDOUT_PATH = "./tasks/holdout"


class HoldoutManager:
    """
    비공개 hold-out 태스크 세트를 생성·저장·로드한다.

    generate_and_save(generator)  → 새 hold-out 세트를 LLM으로 생성 후 저장
    load_latest()                 → 가장 최근 hold-out 세트를 로드
    load(version)                 → 특정 버전 로드
    list_versions()               → 저장된 버전 목록
    """

    def __init__(self, holdout_path: str = DEFAULT_HOLDOUT_PATH):
        self.path = Path(holdout_path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._ensure_gitignore()

    # ── 생성 및 저장 ──────────────────────────────────────────────────

    def generate_and_save(
        self,
        generator: "TaskGenerator",
        label: str = "",
    ) -> Path:
        """
        TaskGenerator로 새 hold-out 세트를 생성하고 저장한다.
        저장 경로: tasks/holdout/holdout_{timestamp}_{seed}.json

        Returns:
            저장된 파일 경로
        """
        print("[HoldoutManager] Hold-out 태스크 생성 중...")
        all_tasks = generator.generate_all()

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"holdout_{timestamp}_{generator.seed}"
        if label:
            filename += f"_{label}"
        filename += ".json"

        data = {
            "version": filename,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seed": generator.seed,
            "label": label,
            "generator_model": generator.model.name,
            "tasks": all_tasks,
            "task_counts": {axis: len(tasks) for axis, tasks in all_tasks.items()},
        }

        filepath = self.path / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        total = sum(len(t) for t in all_tasks.values())
        print(f"[HoldoutManager] 저장 완료: {filepath} ({total}개 태스크)")
        return filepath

    # ── 로드 ──────────────────────────────────────────────────────────

    def load_latest(self) -> dict[str, list[dict]]:
        """가장 최근에 생성된 hold-out 세트를 반환한다."""
        versions = self._sorted_versions()
        if not versions:
            raise FileNotFoundError(
                f"Hold-out 세트가 없습니다. "
                f"'python main.py generate-holdout --model <model>' 을 먼저 실행하세요."
            )
        return self._load_file(versions[-1])

    def load(self, version: str) -> dict[str, list[dict]]:
        """특정 버전 파일명으로 hold-out 세트를 로드한다."""
        filepath = self.path / version
        if not filepath.exists():
            raise FileNotFoundError(f"Hold-out 파일 없음: {filepath}")
        return self._load_file(filepath)

    def list_versions(self) -> list[dict]:
        """저장된 hold-out 버전 목록을 반환한다."""
        versions = self._sorted_versions()
        result = []
        for f in versions:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                result.append({
                    "filename": f.name,
                    "created_at": data.get("created_at", "?"),
                    "seed": data.get("seed", "?"),
                    "label": data.get("label", ""),
                    "generator_model": data.get("generator_model", "?"),
                    "task_counts": data.get("task_counts", {}),
                })
            except Exception:
                continue
        return result

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────

    def _sorted_versions(self) -> list[Path]:
        return sorted(self.path.glob("holdout_*.json"))

    @staticmethod
    def _load_file(filepath: Path) -> dict[str, list[dict]]:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return data.get("tasks", {})

    def _ensure_gitignore(self) -> None:
        """holdout 디렉터리 안에 .gitignore를 생성해 내용물을 숨긴다."""
        gitignore = self.path / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("# Hold-out tasks — never commit\n*\n!.gitignore\n")
