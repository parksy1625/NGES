"""NGES 결과 리포트 출력 (rich 터미널 + JSON 저장)."""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from .calculator import NGESResult

# rich 없이도 최소 동작하도록 fallback 처리
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False

GRADE_COLORS = {
    "S": "bold magenta",
    "A": "bold green",
    "B": "green",
    "C": "yellow",
    "D": "red",
    "F": "bold red",
}

NGI_LABEL = {
    None:        "N/A (첫 사이클)",
    "positive":  "성장 중",
    "flat":      "정체",
    "negative":  "퇴행",
}


def _ngi_label(ngi: Optional[float]) -> str:
    if ngi is None:
        return "N/A (첫 사이클)"
    if ngi >= 2.0:
        return f"{ngi:+.2f}/사이클 — 매우 빠른 성장"
    if ngi >= 1.0:
        return f"{ngi:+.2f}/사이클 — 건강한 성장"
    if ngi >= 0.1:
        return f"{ngi:+.2f}/사이클 — 완만한 성장"
    if ngi >= 0.0:
        return f"{ngi:+.2f}/사이클 — 정체"
    return f"{ngi:+.2f}/사이클 — 퇴행 (원인 분석 필요)"


# ── rich 버전 ─────────────────────────────────────────────────────────

def print_report(result: NGESResult) -> None:
    if _HAS_RICH:
        _rich_report(result)
    else:
        _plain_report(result)


def print_history_report(all_cycles: list[dict], model_name: str) -> None:
    if _HAS_RICH:
        _rich_history(all_cycles, model_name)
    else:
        _plain_history(all_cycles, model_name)


# ── rich 구현 ─────────────────────────────────────────────────────────

def _rich_report(result: NGESResult) -> None:
    console = Console()
    grade_color = GRADE_COLORS.get(result.grade, "white")

    # 헤더
    console.print(Panel(
        f"[bold]모델:[/bold] {result.model_name}   "
        f"[bold]사이클:[/bold] {result.cycle}   "
        f"[bold]시각:[/bold] {result.timestamp[:19].replace('T', ' ')} UTC",
        title="[bold cyan]NGES Benchmark Report[/bold cyan]",
        border_style="cyan",
    ))

    # Axis 상세 테이블
    table = Table(
        title="Axis 세부 점수",
        show_lines=True,
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("Axis", style="bold", width=6)
    table.add_column("항목",            width=22)
    table.add_column("점수",  justify="right", width=8)
    table.add_column("만점",  justify="right", width=6)
    table.add_column("달성률", justify="right", width=8)

    def pct(score, max_):
        return f"{score / max_ * 100:.0f}%"

    def add_row(axis, name, score, max_):
        table.add_row(axis, name, f"{score:.1f}", str(max_), pct(score, max_))

    # Axis A
    add_row("A1", "문제 해결 정확도",   result.a1, 30)
    add_row("A2", "추론 품질",          result.a2, 25)
    add_row("A3", "기억 회수 정확성",   result.a3, 20)
    add_row("A4", "응답 일관성",        result.a4, 15)
    add_row("A5", "장기 목표 유지력",   result.a5, 10)
    table.add_row("", "[bold]Axis A 합계[/bold]",
                  f"[bold]{result.axis_a:.1f}[/bold]", "100",
                  f"[bold]{result.axis_a:.0f}%[/bold]")
    table.add_section()

    # Axis B
    add_row("B1", "개선 속도",          result.b1, 25)
    add_row("B2", "피드백 반응성",      result.b2, 20)
    add_row("B3", "새 환경 적응력",     result.b3, 20)
    add_row("B4", "자가 수정 효과",     result.b4, 20)
    add_row("B5", "성장 누적성",        result.b5, 15)
    table.add_row("", "[bold]Axis B 합계[/bold]",
                  f"[bold]{result.axis_b:.1f}[/bold]", "100",
                  f"[bold]{result.axis_b:.0f}%[/bold]")
    table.add_section()

    # Axis C
    add_row("C1", "자원 대비 성능",     result.c1, 35)
    add_row("C2", "모듈 협업 효율",     result.c2, 35)
    add_row("C3", "복잡도 안정성",      result.c3, 30)
    table.add_row("", "[bold]Axis C 합계[/bold]",
                  f"[bold]{result.axis_c:.1f}[/bold]", "100",
                  f"[bold]{result.axis_c:.0f}%[/bold]")

    console.print(table)

    # 자원 통계
    if result.avg_response_time_ms > 0:
        console.print(
            f"  [dim]평균 응답 시간: {result.avg_response_time_ms:.0f}ms   "
            f"평균 메모리 증분: {result.avg_memory_mb:.1f}MB[/dim]"
        )

    # 최종 점수
    ngi_text = _ngi_label(result.ngi)
    console.print(Panel(
        f"[bold]NGES 총점: {result.nges_total:.2f} / 100[/bold]\n"
        f"등급: [{grade_color}]{result.grade}[/{grade_color}]\n"
        f"NGI: {ngi_text}",
        title="[bold]최종 결과[/bold]",
        border_style=grade_color,
    ))

    # 실행 오류 경고
    errors = [e for e in result.execution_log if e.get("status") == "error"]
    if errors:
        console.print(f"[yellow]⚠ 실행 오류 {len(errors)}건:[/yellow]")
        for e in errors:
            console.print(f"  [red]{e['module']}[/red]: {e.get('error_msg', '')}")


def _rich_history(all_cycles: list[dict], model_name: str) -> None:
    console = Console()
    if not all_cycles:
        console.print(f"[yellow]'{model_name}' 의 저장된 사이클이 없습니다.[/yellow]")
        return

    table = Table(
        title=f"{model_name} — 전체 사이클 이력",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("사이클",  justify="right")
    table.add_column("Axis A",  justify="right")
    table.add_column("Axis B",  justify="right")
    table.add_column("Axis C",  justify="right")
    table.add_column("NGES",    justify="right")
    table.add_column("등급",    justify="center")
    table.add_column("NGI",     justify="right")

    for c in all_cycles:
        grade = c.get("grade", "?")
        color = GRADE_COLORS.get(grade, "white")
        ngi   = c.get("ngi")
        ngi_s = f"{ngi:+.2f}" if ngi is not None else "-"

        table.add_row(
            str(c.get("cycle", "?")),
            f"{c.get('axis_a', 0):.1f}",
            f"{c.get('axis_b', 0):.1f}",
            f"{c.get('axis_c', 0):.1f}",
            f"{c.get('nges_total', 0):.2f}",
            f"[{color}]{grade}[/{color}]",
            ngi_s,
        )

    console.print(table)

    # 간단 ASCII 추세
    scores = [c.get("nges_total", 0) for c in all_cycles]
    _ascii_sparkline(console, scores)


def _ascii_sparkline(console, scores: list[float]) -> None:
    """간단한 ASCII 막대 차트 출력."""
    if len(scores) < 2:
        return
    max_s = max(scores) if max(scores) > 0 else 100
    bar_width = 30
    console.print("\n[dim]NGES 추세:[/dim]")
    for i, s in enumerate(scores):
        filled = int((s / max_s) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        console.print(f"  사이클 {i+1:>3}: [{bar}] {s:.1f}")


# ── 폴백 plain 텍스트 버전 ────────────────────────────────────────────

def _plain_report(result: NGESResult) -> None:
    sep = "=" * 60
    print(sep)
    print("NGES Benchmark Report")
    print(f"모델: {result.model_name}  사이클: {result.cycle}")
    print(sep)
    print(f"A1 문제 해결: {result.a1:.1f}/30  A2 추론: {result.a2:.1f}/25")
    print(f"A3 기억:      {result.a3:.1f}/20  A4 일관성: {result.a4:.1f}/15  A5 목표: {result.a5:.1f}/10")
    print(f"Axis A: {result.axis_a:.1f}/100")
    print(f"B1: {result.b1:.1f}/25  B2: {result.b2:.1f}/20  B3: {result.b3:.1f}/20")
    print(f"B4: {result.b4:.1f}/20  B5: {result.b5:.1f}/15")
    print(f"Axis B: {result.axis_b:.1f}/100")
    print(f"C1: {result.c1:.1f}/35  C2: {result.c2:.1f}/35  C3: {result.c3:.1f}/30")
    print(f"Axis C: {result.axis_c:.1f}/100")
    print(sep)
    print(f"NGES 총점: {result.nges_total:.2f}/100  등급: {result.grade}")
    print(f"NGI: {_ngi_label(result.ngi)}")
    print(sep)


def _plain_history(all_cycles: list[dict], model_name: str) -> None:
    if not all_cycles:
        print(f"'{model_name}' 의 저장된 사이클이 없습니다.")
        return
    print(f"\n{model_name} — 전체 사이클 이력")
    print(f"{'사이클':>6}  {'A':>6}  {'B':>6}  {'C':>6}  {'NGES':>7}  {'등급':>4}  {'NGI':>7}")
    for c in all_cycles:
        ngi = c.get("ngi")
        ngi_s = f"{ngi:+.2f}" if ngi is not None else "   -"
        print(
            f"{c.get('cycle', '?'):>6}  "
            f"{c.get('axis_a', 0):>6.1f}  "
            f"{c.get('axis_b', 0):>6.1f}  "
            f"{c.get('axis_c', 0):>6.1f}  "
            f"{c.get('nges_total', 0):>7.2f}  "
            f"{c.get('grade', '?'):>4}  "
            f"{ngi_s:>7}"
        )
