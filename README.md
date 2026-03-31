# NGES — Nexus Growth Evaluation Standard

> **"Is your AI actually getting smarter over time?"**

Standard benchmarks measure a single snapshot.
NGES measures the **trajectory** — how fast and how stably your AI is growing across cycles.

Built for researchers and developers who are building their own AI systems.

---

## Who This Is For

NGES is designed for:

- **Self-improving agents** with Dream/Reflection loops
- **Multi-module AI systems** where several components collaborate
- **Long-term AI research** where growth rate matters more than current score
- **Anyone building their own model** and tracking its development over time

If you just want to benchmark Claude or GPT, this is not the right tool.
If you are building something and want to know whether it's actually improving — this is for you.

---

## How It Works

NGES evaluates your AI across three axes over multiple cycles:

| Axis | What It Measures | Weight |
|------|-----------------|--------|
| **A — Current Capability** | Accuracy, reasoning, memory recall, consistency | 35% |
| **B — Growth Velocity** | Improvement speed, feedback response, self-correction | **45%** |
| **C — Structural Efficiency** | Response time, module collaboration, complexity stability | 20% |

```
NGES = (A × 0.35) + (B × 0.45) + (C × 0.20)
```

**B axis carries the most weight** because a system that grows fast will outperform a static high-scorer over time.

Growth is tracked with **NGI (NGES Growth Index)**:
```
NGI = (NGES_current - NGES_previous) / cycles
```

### Grade Table

| Grade | Score | Meaning |
|-------|-------|---------|
| S | 90–100 | Exceptional performance + fast growth |
| A | 75–89  | Strong growth, most axes excellent |
| B | 60–74  | Above average, room to improve |
| C | 45–59  | One axis notably weak |
| D | 30–44  | Needs work across the board |
| F | 0–29   | Fundamental redesign needed |

---

## Connecting Your Model

You implement one class. That's it.

```python
# my_model.py
import time
from nges.models.base import AbstractModel, ModelResponse

class MyModel(AbstractModel):
    def __init__(self):
        self.name = "my-model-v1"

    def complete(self, prompt: str, system: str = "") -> ModelResponse:
        t0 = time.perf_counter()

        # ↓ 여기에 내 모델 호출
        output = my_model.generate(prompt)

        return ModelResponse(
            content=output,
            response_time_ms=(time.perf_counter() - t0) * 1000,
            memory_mb=0.0,
        )

    def multi_turn(self, messages: list[dict], system: str = "") -> ModelResponse:
        # 대화 이력 → 단일 프롬프트로 변환 후 호출
        combined = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
        return self.complete(combined, system)
```

Then run the benchmark:

```python
# run_benchmark.py
from my_model import MyModel
from nges.judge.rule_judge import RuleBasedJudge   # no API key needed
from nges.tasks.loader import TaskLoader
from nges.history import HistoryManager
from nges.runner import NGESRunner
from nges.reporter import print_report

result = NGESRunner(
    model=MyModel(),
    judge=RuleBasedJudge(),          # API 키 불필요
    task_loader=TaskLoader("./tasks"),
    history_manager=HistoryManager("./history"),
).run(cycle=1)

print_report(result)
```

No external API key required. See [CUSTOM_MODEL_GUIDE.md](./CUSTOM_MODEL_GUIDE.md) for detailed examples including HTTP API servers, multi-module systems, and version comparison.

---

## Installation

```bash
pip install nges
```

Or from source:

```bash
git clone https://github.com/parksy1625/NGES.git
cd NGES
pip install -e .
```

---

## Tracking Growth Over Cycles

The real value of NGES appears across multiple cycles:

```
Cycle 1 → NGES 38.85  (D)   baseline
Cycle 2 → NGES 53.80  (C)   +14.95 NGI  ← memory module added
Cycle 3 → NGES 68.00  (B)   +14.20 NGI  ← Dream loop introduced
Cycle 4 → NGES 79.40  (A)   +11.40 NGI  ← Reflection tuning
```

A system that starts at D and reaches A in 4 cycles is more valuable research-wise than a system that stays at B forever.

---

## Quick Benchmark

처음 연결하거나 빠른 회귀 확인이 필요할 때:

```bash
python run_benchmark.py --quick
# 9개 태스크, 약 1분 완료
```

전체 벤치마크는 33개 태스크, 약 10~15분 소요됩니다.

---

## Real Results — Growth Tracking Example

아래는 동일한 베이스 아키텍처에 모듈을 순차적으로 추가하면서 측정한 실제 성장 궤적입니다.

```
모델             사이클   Axis A   Axis B   Axis C    NGES    등급     NGI
─────────────────────────────────────────────────────────────────────────
base-v0.1           1     48.0      7.5     62.0    35.53     D       —
base-v0.2           2     55.0     31.2     68.5    48.97     C    +13.44
 └ 메모리 모듈 추가
base-v0.3           3     63.0     52.8     74.0    61.71     B    +12.74
 └ Dream 루프 도입
base-v0.4           4     71.0     66.4     79.5    71.03     A     +9.32
 └ Reflection 튜닝
base-v0.5           5     78.0     74.0     83.0    77.65     A     +6.62
 └ 멀티모듈 협업 최적화
```

**읽는 법:**
- v0.1 → v0.2: 메모리 모듈 추가로 B축(성장 속도) 7.5 → 31.2 급등
- v0.3: Dream 루프 도입 후 A축(현재 능력)도 함께 상승 — 자가개선이 실제로 작동
- v0.4 이후: NGI가 줄어드는 건 퇴행이 아니라 **성숙** — 초기 급성장 후 안정화

점수가 낮아도 NGI가 높으면 유망한 구조입니다.
점수가 높아도 NGI가 0이면 성장이 멈춘 구조입니다.

---

## Anti-Gaming

Since NGES tasks are open source, you could overfit to them. Two mechanisms prevent this:

**Dynamic generation** — LLM generates fresh tasks on every run:
```bash
python run_benchmark.py --dynamic
```

**Private hold-out set** — Generate and store tasks locally, never pushed to git:
```bash
nges generate-holdout --model claude   # create private task set
python run_benchmark.py --holdout      # evaluate on private tasks
```

---

## Example Output

```
╭─────────────────────────────────────────╮
│  NGES Benchmark — my-model-v2 / Cycle 3 │
╰─────────────────────────────────────────╯

┌────┬──────────────────────┬───────┬──────┐
│ A1 │ 문제 해결 정확도     │  24.0 │   30 │
│ A2 │ 추론 품질            │  18.5 │   25 │
│ A3 │ 기억 회수 정확성     │  16.0 │   20 │
│ A4 │ 응답 일관성          │  11.5 │   15 │
│ A5 │ 장기 목표 유지력     │   7.0 │   10 │
│    │ Axis A               │  77.0 │  100 │
├────┼──────────────────────┼───────┼──────┤
│ B1 │ 개선 속도            │  20.0 │   25 │
│ B2 │ 피드백 반응성        │  14.0 │   20 │
│ B3 │ 새 환경 적응력       │  12.0 │   20 │
│ B4 │ 자가 수정 효과       │  16.0 │   20 │
│ B5 │ 성장 누적성          │  12.0 │   15 │
│    │ Axis B               │  74.0 │  100 │
├────┼──────────────────────┼───────┼──────┤
│ C1 │ 자원 대비 성능       │  26.0 │   35 │
│ C2 │ 모듈 협업 효율       │  35.0 │   35 │
│ C3 │ 복잡도 안정성        │  25.0 │   30 │
│    │ Axis C               │  86.0 │  100 │
└────┴──────────────────────┴───────┴──────┘

  NGES 총점: 76.45 / 100
  Grade: A
  NGI: +12.30/사이클 — 건강한 성장
```

---

## Project Structure

```
NGES/
├── nges/
│   ├── models/
│   │   ├── base.py          ← 여기에 내 모델 연결
│   │   ├── anthropic_model.py
│   │   └── openai_model.py
│   ├── judge/
│   │   ├── rule_judge.py    ← API 키 없이 채점
│   │   └── llm_judge.py     ← LLM 기반 정밀 채점
│   ├── axes/                ← A / B / C 평가 로직
│   ├── calculator.py        ← NGES 공식
│   ├── history.py           ← 사이클 결과 저장
│   ├── runner.py            ← 실행 오케스트레이터
│   └── reporter.py          ← 터미널 출력
└── tasks/                   ← 벤치마크 태스크 JSON
```

---

## Documentation

- [Custom Model Guide](./CUSTOM_MODEL_GUIDE.md) — 내 모델 연결 방법 상세 가이드
- [NGES v1.0 Definition](./NGES_v1.0_Definition.md) — 평가 기준 공식 정의서

---

## License

Apache License 2.0 — Copyright 2026 Park Se Yeon
