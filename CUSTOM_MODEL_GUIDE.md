# NGES Custom Model Guide

NGES는 **본인이 만든 AI 시스템**을 평가하기 위한 도구입니다.

Claude나 GPT 같은 외부 API를 평가하는 것이 목적이 아닙니다.
자체 개발한 모델, 에이전트, 멀티모듈 시스템을 NGES에 연결해서
시간에 따른 성장을 측정하는 것이 핵심입니다.

---

## 연결 구조

```
내 AI 시스템
     ↓
AbstractModel 구현 (어댑터 작성)
     ↓
NGES 벤치마크 실행
     ↓
성장 지표 측정 (NGES 점수, NGI)
```

Anthropic/OpenAI 어댑터는 **Judge 모델 전용**으로만 사용됩니다.
(응답 품질을 채점하는 역할 — API 키가 없으면 rule-based judge로 대체 가능)

---

## AbstractModel 인터페이스

```python
# nges/models/base.py

@dataclass
class ModelResponse:
    content: str                    # 모델의 응답 텍스트
    input_tokens: Optional[int]     # 입력 토큰 수 (없으면 None)
    output_tokens: Optional[int]    # 출력 토큰 수 (없으면 None)
    response_time_ms: float         # 응답 시간 (C1 자원 측정용)
    memory_mb: float                # 메모리 사용량 (C1 자원 측정용)


class AbstractModel(ABC):
    name: str                       # 모델 식별자 (히스토리 파일명에 사용)

    def complete(self, prompt: str, system: str = "") -> ModelResponse:
        """단일 프롬프트 → 응답"""
        ...

    def multi_turn(self, messages: list[dict], system: str = "") -> ModelResponse:
        """
        대화 이력 포함 → 응답 (A3 기억 회수, A5 목표 유지 평가용)
        messages: [{"role": "user"/"assistant", "content": "..."}]
        """
        ...
```

---

## 예제 1 — HTTP API 서버로 돌아가는 모델

로컬에 REST API 서버로 모델을 띄워놓은 경우:

```python
# my_model.py
import time
import requests
from nges.models.base import AbstractModel, ModelResponse

class MyLocalModel(AbstractModel):
    def __init__(self, endpoint: str = "http://localhost:8000"):
        self.endpoint = endpoint
        self.name = "my-local-model"

    def complete(self, prompt: str, system: str = "") -> ModelResponse:
        t0 = time.perf_counter()

        resp = requests.post(f"{self.endpoint}/generate", json={
            "prompt": prompt,
            "system": system,
        })
        resp.raise_for_status()

        elapsed_ms = (time.perf_counter() - t0) * 1000
        data = resp.json()

        return ModelResponse(
            content=data["text"],
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            response_time_ms=elapsed_ms,
            memory_mb=0.0,
        )

    def multi_turn(self, messages: list[dict], system: str = "") -> ModelResponse:
        t0 = time.perf_counter()

        resp = requests.post(f"{self.endpoint}/chat", json={
            "messages": messages,
            "system": system,
        })
        resp.raise_for_status()

        elapsed_ms = (time.perf_counter() - t0) * 1000
        data = resp.json()

        return ModelResponse(
            content=data["text"],
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            response_time_ms=elapsed_ms,
            memory_mb=0.0,
        )
```

실행:

```python
# run_benchmark.py
from my_model import MyLocalModel
from nges.judge.llm_judge import LLMJudge
from nges.tasks.loader import TaskLoader
from nges.history import HistoryManager
from nges.runner import NGESRunner
from nges.reporter import print_report

model = MyLocalModel("http://localhost:8000")

# Judge: API 키가 있으면 외부 모델, 없으면 아래 RuleBasedJudge 사용
from nges.judge.rule_judge import RuleBasedJudge
judge = RuleBasedJudge()

runner = NGESRunner(
    model=model,
    judge=judge,
    task_loader=TaskLoader("./tasks"),
    history_manager=HistoryManager("./history"),
)

result = runner.run(cycle=1)
print_report(result)
```

---

## 예제 2 — Python 함수로 직접 연결

모델이 Python 함수/클래스로 되어 있는 경우:

```python
# my_model.py
import time
import os
import psutil
from nges.models.base import AbstractModel, ModelResponse

# 내 모델 임포트 (예시)
from nexus_ai import NexusCore

class NexusModel(AbstractModel):
    def __init__(self, checkpoint_path: str):
        self.model = NexusCore.load(checkpoint_path)
        self.name = f"nexus:{checkpoint_path}"
        self._proc = psutil.Process(os.getpid())

    def complete(self, prompt: str, system: str = "") -> ModelResponse:
        mem_before = self._proc.memory_info().rss / 1024 ** 2
        t0 = time.perf_counter()

        # 내 모델 호출
        output = self.model.generate(
            prompt=prompt,
            system_prompt=system,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        mem_after = self._proc.memory_info().rss / 1024 ** 2

        return ModelResponse(
            content=output.text,
            input_tokens=None,
            output_tokens=None,
            response_time_ms=elapsed_ms,
            memory_mb=max(0.0, mem_after - mem_before),
        )

    def multi_turn(self, messages: list[dict], system: str = "") -> ModelResponse:
        # 대화 이력을 단일 프롬프트로 변환 (모델이 multi-turn을 지원 안 할 경우)
        combined = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in messages
        )
        return self.complete(combined, system=system)
```

---

## 예제 3 — API 키 없이 Rule-based Judge 사용

외부 LLM API 없이 순수하게 내 모델만으로 벤치마크를 실행하려면
`RuleBasedJudge`를 사용합니다.

주관적 평가(A2 추론 품질, A5 목표 유지력 등)는 키워드/길이 기반으로 채점되므로
정밀도가 낮아지지만, **API 키 없이 완전 독립 실행**이 가능합니다.

```python
from nges.judge.rule_judge import RuleBasedJudge

judge = RuleBasedJudge()

runner = NGESRunner(
    model=my_model,
    judge=judge,          # API 키 불필요
    task_loader=...,
    history_manager=...,
)
```

---

## 예제 4 — 빠른 테스트 (퀵 모드)

처음 연결할 때 전체 33개 태스크를 돌리기 전에,
A1 태스크 3개만 빠르게 확인하고 싶으면:

```python
from nges.tasks.loader import TaskLoader

class QuickLoader:
    """A1 태스크 3개만 사용하는 빠른 테스트 로더."""
    def load(self, axis):
        if axis == "A1":
            return TaskLoader("./tasks").load("A1")[:3]
        return []
    def load_all(self):
        return {"A1": self.load("A1"), "A2": [], "A3": [],
                "A4": [], "A5": [], "B3": []}

runner = NGESRunner(model=my_model, judge=judge,
                    task_loader=QuickLoader(), ...)
```

---

## 멀티모듈 시스템 연결

Nexus AI처럼 여러 모듈이 협력하는 구조라면,
전체 시스템을 하나의 `AbstractModel`로 감싸서 연결합니다.

```python
class NexusMultiModuleModel(AbstractModel):
    """
    Dream 모듈 + Memory 모듈 + Reasoning 모듈이 협력하는 구조.
    외부에서 보면 하나의 모델처럼 동작.
    """
    def __init__(self):
        self.memory = MemoryModule()
        self.reasoning = ReasoningModule()
        self.dream = DreamModule()
        self.name = "nexus-multimodule"

    def complete(self, prompt: str, system: str = "") -> ModelResponse:
        t0 = time.perf_counter()

        # 메모리에서 관련 컨텍스트 로드
        context = self.memory.retrieve(prompt)

        # 추론 모듈로 응답 생성
        response = self.reasoning.generate(prompt, context=context, system=system)

        # 메모리에 저장
        self.memory.store(prompt, response.text)

        return ModelResponse(
            content=response.text,
            response_time_ms=(time.perf_counter() - t0) * 1000,
            memory_mb=0.0,
        )
```

Dream/Reflection 루프 적용 후 성능 변화는 B4 항목이 자동으로 측정합니다.

---

## 버전별 성장 추적

사이클마다 다른 체크포인트를 연결해서 버전 간 성장을 비교할 수 있습니다.

```bash
# v0.1 체크포인트 평가
python run_benchmark.py --checkpoint ./checkpoints/v0.1 --cycle 1

# v0.2 체크포인트 평가
python run_benchmark.py --checkpoint ./checkpoints/v0.2 --cycle 2

# 성장 이력 확인
nges report --model nexus:v0.2
```

```
사이클   Axis A   Axis B   Axis C    NGES    등급    NGI
     1    52.0     7.5     67.5    38.85     D      -
     2    61.0    34.2     71.0    53.80     C    +14.95
     3    74.0    58.4     79.0    68.00     B    +14.20
```

NGI +14점/사이클 → 빠른 성장 중.

---

## 요약

| 상황 | 방법 |
|------|------|
| HTTP API 서버 모델 | `requests.post()` 래핑 |
| Python 함수/클래스 모델 | 직접 호출 래핑 |
| API 키 없이 실행 | `RuleBasedJudge()` 사용 |
| 빠른 연결 테스트 | `QuickLoader()` 사용 |
| 멀티모듈 시스템 | 전체를 하나의 `AbstractModel`로 감싸기 |

구현한 어댑터는 `nges/models/` 에 추가하면 자동으로 인식됩니다.
