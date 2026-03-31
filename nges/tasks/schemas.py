"""각 Axis별 태스크 생성 스키마 (LLM에게 전달할 지시 템플릿)."""

from __future__ import annotations

# ── 공통 출력 형식 지시 ────────────────────────────────────────────────

GENERATOR_SYSTEM = """You are a benchmark task generator for the NGES (Nexus Growth Evaluation Standard).

Your job is to generate evaluation tasks that test AI capabilities.

Rules:
1. Output ONLY a valid JSON array of task objects. No markdown, no explanation.
2. Each task must exactly follow the schema provided.
3. Tasks must be novel — do not copy or paraphrase well-known benchmark questions.
4. Vary difficulty, domain, and question style across tasks.
5. For answer_check "exact" or "contains", ensure expected_answer is unambiguous.
6. For answer_check "llm_judge", write a clear, specific rubric."""

# ── A1: 문제 해결 정확도 ──────────────────────────────────────────────

A1_SCHEMA = {
    "system": GENERATOR_SYSTEM,
    "prompt": """Generate {n} problem-solving tasks for the A1 axis (problem-solving accuracy).

Mix these types:
- multiple_choice (math, logic, science, geography) — include 4 options A/B/C/D, one correct
- open_ended (reasoning, factual) — short unambiguous answer
- code_generation (Python functions) — use answer_check "llm_judge" with a rubric

Output format (JSON array):
[
  {{
    "id": "a1_gen_{seed}_{i}",
    "type": "multiple_choice",
    "domain": "math",
    "difficulty": 3,
    "prompt": "...",
    "expected_answer": "B",
    "answer_check": "contains"
  }},
  {{
    "id": "a1_gen_{seed}_{i}",
    "type": "code_generation",
    "domain": "programming",
    "difficulty": 4,
    "prompt": "...",
    "rubric": "...",
    "answer_check": "llm_judge"
  }}
]

Generate {n} tasks. Vary domains and difficulties (1-5).""",
}

# ── A2: 추론 품질 ─────────────────────────────────────────────────────

A2_SCHEMA = {
    "system": GENERATOR_SYSTEM,
    "prompt": """Generate {n} reasoning quality tasks for the A2 axis.

Use these reasoning types:
- causal_reasoning: cause-and-effect analysis
- deductive_reasoning: syllogism or logical deduction
- analogical_reasoning: analogy completion with explanation
- multi_step_logic: chained logical inference
- counterfactual_reasoning: "what if X had not happened"

All tasks use answer_check "llm_judge". Write specific rubrics.

Output format (JSON array):
[
  {{
    "id": "a2_gen_{seed}_{i}",
    "domain": "causal_reasoning",
    "difficulty": 3,
    "prompt": "...",
    "rubric": "Award 1.0 if: ... Award 0.5 if: ... Award 0.0 if: ...",
    "answer_check": "llm_judge"
  }}
]

Generate {n} tasks.""",
}

# ── A3: 기억 회수 ─────────────────────────────────────────────────────

A3_SCHEMA = {
    "system": GENERATOR_SYSTEM,
    "prompt": """Generate {n} memory recall tasks for the A3 axis.

Each task injects a piece of information and later asks the model to recall it.
Use realistic contexts: project specs, customer records, meeting notes, config values, event details.

Output format (JSON array):
[
  {{
    "id": "a3_gen_{seed}_{i}",
    "memory_injection": "...",
    "recall_prompt": "...",
    "expected_contains": "...",
    "delay_turns": 3
  }}
]

Rules:
- memory_injection should contain 2-4 distinct facts
- recall_prompt should ask for one specific fact
- expected_contains must be a short unique substring of the fact
- delay_turns: vary between 2 and 6

Generate {n} tasks.""",
}

# ── A4: 응답 일관성 ───────────────────────────────────────────────────

A4_SCHEMA = {
    "system": GENERATOR_SYSTEM,
    "prompt": """Generate {n} consistency tasks for the A4 axis.

These are questions that have a single correct, stable answer.
Use factual, math, or yes/no questions where the answer never changes.

Output format (JSON array):
[
  {{
    "id": "a4_gen_{seed}_{i}",
    "domain": "factual",
    "difficulty": 2,
    "prompt": "...",
    "answer_check": "contains",
    "expected_answer": "..."
  }}
]

Rules:
- Answers must be unambiguous and universally agreed upon
- Avoid questions where phrasing could lead to different valid answers
- Mix factual, math, and definition-style questions

Generate {n} tasks.""",
}

# ── A5: 장기 목표 유지력 ──────────────────────────────────────────────

A5_SCHEMA = {
    "system": GENERATOR_SYSTEM,
    "prompt": """Generate {n} goal tracking scenarios for the A5 axis.

Each scenario has:
1. A clear initial goal with a specific constraint (budget, word count, target audience, etc.)
2. 3-4 conversation turns that try to distract or deviate from the goal
3. A final check question
4. A rubric evaluating whether the goal was maintained

Output format (JSON array):
[
  {{
    "id": "a5_gen_{seed}_{i}",
    "goal_statement": "...",
    "prompt": "...",
    "conversation_turns": [
      {{"role": "user", "content": "..."}},
      {{"role": "user", "content": "..."}}
    ],
    "final_check": "...",
    "rubric": "Award 1.0 if: ... Award 0.5 if: ... Award 0.0 if: ...",
    "answer_check": "llm_judge"
  }}
]

Generate {n} scenario(s). Make the distractors tempting but clearly off-goal.""",
}

# ── B3: 새 환경 적응력 ────────────────────────────────────────────────

B3_SCHEMA = {
    "system": GENERATOR_SYSTEM,
    "prompt": """Generate {n} novel domain adaptation tasks for the B3 axis.

Choose UNUSUAL or NICHE domains that are unlikely to be in standard training data.
Group tasks in pairs by domain (2 tasks per domain) so adaptation curve can be measured.

Suggested domains (pick different ones each time):
- Ethnomusicology, Byzantine law, Cryovolcanism, Actuarial science,
  Paleoclimatology, Zymology, Speleology, Computational linguistics,
  Medieval siege engineering, Ichnology

Output format (JSON array):
[
  {{
    "id": "b3_gen_{seed}_{i}",
    "domain": "...",
    "novel": true,
    "difficulty": 4,
    "prompt": "...",
    "rubric": "Award 1.0 if: ... Award 0.5 if: ... Award 0.0 if: ...",
    "answer_check": "llm_judge"
  }}
]

Generate {n} tasks (in domain pairs). Use answer_check "llm_judge" for all.""",
}

# ── Axis별 스키마 매핑 ────────────────────────────────────────────────

AXIS_SCHEMAS: dict[str, dict] = {
    "A1": A1_SCHEMA,
    "A2": A2_SCHEMA,
    "A3": A3_SCHEMA,
    "A4": A4_SCHEMA,
    "A5": A5_SCHEMA,
    "B3": B3_SCHEMA,
}

# 각 Axis의 기본 생성 태스크 수
DEFAULT_TASK_COUNTS: dict[str, int] = {
    "A1": 10,
    "A2": 5,
    "A3": 5,
    "A4": 5,
    "A5": 2,
    "B3": 6,
}
