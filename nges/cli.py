"""NGES CLI — Click 커맨드 그룹 정의."""

from __future__ import annotations
import json
import sys
from pathlib import Path

import click

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


# ── 설정 로드 ─────────────────────────────────────────────────────────

def load_config(config_path: str = "./config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        return {}
    if _HAS_YAML:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    # yaml 없으면 빈 설정
    return {}


# ── CLI 그룹 ──────────────────────────────────────────────────────────

@click.group()
@click.version_option("1.0.0", prog_name="NGES")
def cli():
    """NGES — Nexus Growth Evaluation Standard 벤치마크 도구."""
    pass


# ── run 커맨드 ────────────────────────────────────────────────────────

@cli.command()
@click.option("--model",    required=True,  help="평가할 모델 (예: claude, gpt4o, anthropic:claude-opus-4-6)")
@click.option("--cycle",    default=None,   type=int, help="사이클 번호. 미지정 시 마지막 사이클 + 1 자동 계산")
@click.option("--judge",    default=None,   help="Judge 모델 (미지정 시 config.yaml 기본값 사용)")
@click.option("--tasks",    default=None,   help="태스크 디렉터리 경로 (기본: ./tasks)")
@click.option("--history",  default=None,   help="히스토리 디렉터리 경로 (기본: ./history)")
@click.option("--config",   default="./config.yaml", help="설정 파일 경로")
@click.option("--save-report", is_flag=True, default=False, help="JSON 리포트를 ./reports/ 에 저장")
@click.option("--dynamic",  is_flag=True,   default=False, help="LLM이 태스크를 실행마다 동적 생성 (벤치마크 오염 방지)")
@click.option("--holdout",  is_flag=True,   default=False, help="공개 태스크 대신 비공개 hold-out 세트 사용")
@click.option("--holdout-version", default=None, help="특정 hold-out 버전 파일명 (기본: 최신)")
@click.option("--quick",    is_flag=True,   default=False, help="퀵 모드: 태스크 9개만, 약 1분 완료")
def run(model, cycle, judge, tasks, history, config, save_report, dynamic, holdout, holdout_version, quick):
    """AI 모델을 NGES 기준으로 벤치마크 실행."""
    cfg = load_config(config)

    # 경로 결정
    tasks_path   = tasks   or cfg.get("tasks",   {}).get("path",   "./tasks")
    history_path = history or cfg.get("history", {}).get("path",   "./history")
    reports_path = cfg.get("reports", {}).get("path", "./reports")

    # C1 기준값
    scoring = cfg.get("scoring", {})
    baseline_time = scoring.get("c1_baseline_time_ms", 3000)
    baseline_mem  = scoring.get("c1_baseline_mem_mb",  150)

    # 모듈 임포트 (lazy — 설치 확인)
    try:
        from nges.models.registry import get_model
        from nges.judge.llm_judge import LLMJudge
        from nges.tasks.loader import TaskLoader
        from nges.tasks.quick_loader import QuickLoader
        from nges.tasks.generator import TaskGenerator
        from nges.tasks.holdout import HoldoutManager
        from nges.history import HistoryManager
        from nges.runner import NGESRunner
        from nges.reporter import print_report
    except ImportError as e:
        click.echo(f"[오류] 필요한 패키지가 없습니다: {e}", err=True)
        click.echo("pip install -r requirements.txt 를 먼저 실행하세요.", err=True)
        sys.exit(1)

    # 모델 초기화
    click.echo(f"모델 초기화: {model}")
    try:
        target_model = get_model(model)
    except (ValueError, ImportError) as e:
        click.echo(f"[오류] {e}", err=True)
        sys.exit(1)

    # Judge 모델
    judge_name = judge or cfg.get("judge", {}).get("default_model", model)
    click.echo(f"Judge 모델: {judge_name}")
    try:
        judge_model = get_model(judge_name)
    except (ValueError, ImportError) as e:
        click.echo(f"[경고] Judge 모델 초기화 실패 ({e}), 피평가 모델을 Judge로 사용합니다.", err=True)
        judge_model = target_model

    llm_judge = LLMJudge(judge_model)

    # 히스토리 초기화
    history_mgr = HistoryManager(history_path)

    # ── 태스크 소스 결정 ──────────────────────────────────────────────
    if holdout and dynamic:
        click.echo("[오류] --holdout 과 --dynamic 은 동시에 사용할 수 없습니다.", err=True)
        sys.exit(1)

    if dynamic:
        click.echo("[동적 생성 모드] LLM이 태스크를 생성합니다...")
        generator = TaskGenerator(target_model)
        all_tasks = generator.generate_all()
        click.echo(f"  시드: {generator.seed}  |  총 {sum(len(v) for v in all_tasks.values())}개 태스크 생성됨")

        class _DynamicLoader:
            def load(self, axis): return all_tasks.get(axis.upper(), [])
            def load_all(self): return all_tasks

        task_loader = _DynamicLoader()

    elif holdout:
        click.echo("[Hold-out 모드] 비공개 태스크 세트를 사용합니다...")
        holdout_mgr = HoldoutManager(
            str(Path(tasks_path) / "holdout")
        )
        if holdout_version:
            ho_tasks = holdout_mgr.load(holdout_version)
        else:
            ho_tasks = holdout_mgr.load_latest()
        click.echo(f"  {sum(len(v) for v in ho_tasks.values())}개 hold-out 태스크 로드됨")

        class _HoldoutLoader:
            def load(self, axis): return ho_tasks.get(axis.upper(), [])
            def load_all(self): return ho_tasks

        task_loader = _HoldoutLoader()

    elif quick:
        click.echo("[퀵 모드] 9개 태스크로 빠른 벤치마크를 실행합니다...")
        task_loader = QuickLoader(tasks_path)

    else:
        task_loader = TaskLoader(tasks_path)

    # 사이클 번호 결정
    if cycle is None:
        cycle = history_mgr.latest_cycle(target_model.name) + 1
        click.echo(f"사이클 자동 계산: {cycle}")
    else:
        click.echo(f"사이클: {cycle}")

    # 실행
    click.echo(f"\n{'='*50}")
    click.echo(f"NGES 벤치마크 시작 — {target_model.name} / Cycle {cycle}")
    click.echo(f"{'='*50}\n")

    runner = NGESRunner(
        model=target_model,
        judge=llm_judge,
        task_loader=task_loader,
        history_manager=history_mgr,
        baseline_time_ms=baseline_time,
        baseline_mem_mb=baseline_mem,
    )

    try:
        result = runner.run(cycle=cycle)
    except Exception as e:
        click.echo(f"\n[오류] 벤치마크 실행 중 예외 발생: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 리포트 출력
    print_report(result)

    # JSON 저장
    if save_report:
        Path(reports_path).mkdir(parents=True, exist_ok=True)
        report_path = Path(reports_path) / f"{result.model_name.replace(':', '_')}_cycle{result.cycle:04d}_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        click.echo(f"\n리포트 저장: {report_path}")


# ── report 커맨드 ─────────────────────────────────────────────────────

@cli.command()
@click.option("--model",   required=True, help="조회할 모델 이름")
@click.option("--history", default=None,  help="히스토리 디렉터리 경로")
@click.option("--config",  default="./config.yaml")
def report(model, history, config):
    """저장된 모든 사이클의 NGES 이력을 출력한다."""
    cfg = load_config(config)
    history_path = history or cfg.get("history", {}).get("path", "./history")

    try:
        from nges.history import HistoryManager
        from nges.reporter import print_history_report
        from nges.models.registry import get_model
    except ImportError as e:
        click.echo(f"[오류] {e}", err=True)
        sys.exit(1)

    history_mgr = HistoryManager(history_path)

    # 모델 이름 정규화 (registry 통해 name 속성 사용)
    try:
        m = get_model(model)
        model_name = m.name
    except Exception:
        model_name = model

    all_cycles = history_mgr.load_all(model_name)
    print_history_report(all_cycles, model_name)


# ── generate-holdout 커맨드 ───────────────────────────────────────────

@cli.command("generate-holdout")
@click.option("--model",  required=True, help="태스크 생성에 사용할 LLM")
@click.option("--tasks",  default=None,  help="태스크 디렉터리 경로 (기본: ./tasks)")
@click.option("--label",  default="",    help="버전 식별 레이블 (예: v2, sprint3)")
@click.option("--config", default="./config.yaml")
def generate_holdout(model, tasks, label, config):
    """비공개 hold-out 태스크 세트를 LLM으로 생성한다. (git에 올라가지 않음)"""
    cfg = load_config(config)
    tasks_path = tasks or cfg.get("tasks", {}).get("path", "./tasks")

    try:
        from nges.models.registry import get_model
        from nges.tasks.generator import TaskGenerator
        from nges.tasks.holdout import HoldoutManager
    except ImportError as e:
        click.echo(f"[오류] {e}", err=True)
        sys.exit(1)

    click.echo(f"Hold-out 생성 모델: {model}")
    try:
        gen_model = get_model(model)
    except (ValueError, ImportError) as e:
        click.echo(f"[오류] {e}", err=True)
        sys.exit(1)

    generator = TaskGenerator(gen_model)
    holdout_mgr = HoldoutManager(str(Path(tasks_path) / "holdout"))

    filepath = holdout_mgr.generate_and_save(generator, label=label)
    click.echo(f"\nHold-out 세트 저장 완료: {filepath}")
    click.echo("이 파일은 .gitignore로 보호되어 공개 저장소에 올라가지 않습니다.")


# ── list-holdout 커맨드 ────────────────────────────────────────────────

@cli.command("list-holdout")
@click.option("--tasks",  default=None, help="태스크 디렉터리 경로")
@click.option("--config", default="./config.yaml")
def list_holdout(tasks, config):
    """저장된 hold-out 세트 버전 목록을 출력한다."""
    cfg = load_config(config)
    tasks_path = tasks or cfg.get("tasks", {}).get("path", "./tasks")

    try:
        from nges.tasks.holdout import HoldoutManager
    except ImportError as e:
        click.echo(f"[오류] {e}", err=True)
        sys.exit(1)

    holdout_mgr = HoldoutManager(str(Path(tasks_path) / "holdout"))
    versions = holdout_mgr.list_versions()

    if not versions:
        click.echo("저장된 hold-out 세트가 없습니다.")
        click.echo("python main.py generate-holdout --model claude 로 생성하세요.")
        return

    click.echo(f"\n저장된 hold-out 세트 ({len(versions)}개):\n")
    for v in versions:
        counts = v.get("task_counts", {})
        total = sum(counts.values())
        label = f" [{v['label']}]" if v.get("label") else ""
        click.echo(f"  {v['filename']}{label}")
        click.echo(f"    생성: {v['created_at'][:19]}  |  모델: {v['generator_model']}  |  태스크: {total}개")


# ── list-models 커맨드 ────────────────────────────────────────────────

@cli.command("list-models")
def list_models():
    """사용 가능한 모델 단축명 목록을 출력한다."""
    from nges.models.registry import MODEL_REGISTRY
    click.echo("\n사용 가능한 모델 단축명:")
    click.echo(f"  {'단축명':<20} {'Provider':<12} {'Model ID'}")
    click.echo("  " + "-" * 50)
    for alias, (provider, model_id) in MODEL_REGISTRY.items():
        click.echo(f"  {alias:<20} {provider:<12} {model_id}")
    click.echo("\n커스텀 형식: 'provider:model_id' (예: anthropic:claude-opus-4-6)")


