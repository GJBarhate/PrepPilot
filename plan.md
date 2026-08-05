# Build Plan — AI Mock Interview Coach

You are building a complete take-home project from scratch. Follow this plan top to bottom. Create files in the order given in Section 3, and make the git commit listed at the end of each step before moving to the next step.

## Fixed decisions (do not deviate)

- **Python**: 3.11+
- **LLM**: Google Gemini API, free tier. Model string: **`gemini-3.5-flash-lite`** (verified current as of Aug 2026 — the fastest/cheapest GA Flash-Lite tier). Set it once in `src/config.py` as `MODEL_NAME` and never hardcode it elsewhere.
- **SDK**: `google-genai` (the current Gen AI SDK, `from google import genai`). Do **not** use the legacy `google-generativeai` package.
- **Key rotation**: up to 6 keys, `GEMINI_API_KEY_1` … `GEMINI_API_KEY_6` in `.env`, round-robin with fallback on 429 / rate-limit / quota errors.
- **Agents**: exactly 4 — Interviewer, Adaptive Controller, Evaluator, Coach.
- **Interface**: CLI only, `input()`-based. No Streamlit, no Gradio, no web UI.
- **Out of scope, by design** (assignment marks these optional or does not ask for them): no RAG, no web-search grounding, no vector DB, no deployment, no Docker, no demo video, no test suite beyond a smoke script. State this explicitly in the README's "Scope and tradeoffs" section so the reviewer sees it was a decision, not an omission.

---

## 1. Repo folder structure

```
ai-mock-interview-coach/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── main.py
├── prompts/
│   ├── interviewer.md
│   ├── adaptive_controller.md
│   ├── evaluator.md
│   └── coach.md
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── llm_client.py
│   ├── prompt_loader.py
│   ├── state.py
│   ├── orchestrator.py
│   ├── cli.py
│   └── agents/
│       ├── __init__.py
│       ├── base.py
│       ├── interviewer.py
│       ├── adaptive_controller.py
│       ├── evaluator.py
│       └── coach.py
├── scripts/
│   └── simulate_candidate.py
└── transcripts/
    ├── strong_candidate.md
    ├── weak_candidate.md
    └── edge_case_evasive.md
```

## 2. One-line purpose for every file

| File | Purpose |
|---|---|
| `.env.example` | Template listing `GEMINI_API_KEY_1..6` so a reviewer knows exactly what to fill in. |
| `.gitignore` | Excludes `.env`, `__pycache__/`, `*.pyc`, `.venv/`, `transcripts/raw/`. |
| `README.md` | Setup/run instructions, ASCII architecture diagram, design decisions and tradeoffs, links to the three example transcripts. |
| `requirements.txt` | Pinned runtime dependencies. |
| `main.py` | Thin entry point: loads env, builds the orchestrator, hands control to the CLI. |
| `prompts/interviewer.md` | System prompt for the Interviewer agent. |
| `prompts/adaptive_controller.md` | System prompt for the Adaptive Controller agent. |
| `prompts/evaluator.md` | System prompt for the Evaluator agent. |
| `prompts/coach.md` | System prompt for the Coach agent. |
| `src/__init__.py` | Marks `src` as a package. |
| `src/config.py` | Model name, turn bounds, difficulty scale, key env-var names, generation defaults — all tunables in one place. |
| `src/llm_client.py` | Gemini wrapper: multi-key round-robin rotation, 429 fallback, retry/backoff, plain-text and JSON-mode calls. |
| `src/prompt_loader.py` | Reads a prompt file from `prompts/` and caches it, so prompts stay editable without touching code. |
| `src/state.py` | Dataclasses for the interview session: `CandidateProfile`, `Turn`, `Evaluation`, `ControlDecision`, `SessionState`. |
| `src/agents/__init__.py` | Exports the four agent classes. |
| `src/agents/base.py` | Shared `Agent` base: holds the LLM client, its prompt file, and a `run()` contract. |
| `src/agents/interviewer.py` | Generates the next candidate-facing question from the controller's directive and interview history. |
| `src/agents/adaptive_controller.py` | Reads the latest evaluation and decides the next move (probe / move on / adjust difficulty / wrap up) as JSON. |
| `src/agents/evaluator.py` | Scores each answer across multiple dimensions and classifies answer type, as strict JSON. |
| `src/agents/coach.py` | Produces the final markdown feedback report from the full transcript and all evaluations. |
| `src/orchestrator.py` | The interview loop: sequences the four agents, enforces turn bounds, carries state, decides termination. |
| `src/cli.py` | Intake prompts, turn-by-turn I/O, optional live evaluator debug view, saves the transcript. |
| `scripts/simulate_candidate.py` | Drives a full interview with a scripted/LLM-played candidate persona to produce reproducible example transcripts. |
| `transcripts/strong_candidate.md` | Example run: a well-prepared candidate, showing the system raising difficulty and moving on. |
| `transcripts/weak_candidate.md` | Example run: a shallow candidate, showing probing and difficulty easing. |
| `transcripts/edge_case_evasive.md` | Example run: off-topic answers plus "I don't know", showing graceful recovery. |

---

## 3. Step-by-step build sequence

Create and edit files in exactly this order.

### Step 1 — Repo skeleton and dependency pinning

Create the directory tree above with empty `__init__.py` files. Then:

**`requirements.txt`** — keep the dependency surface small; everything else is stdlib.
```
google-genai==2.16.0
python-dotenv==1.1.1
```
If `pip install` fails to resolve either pin, install the latest compatible release and update the pin to the version actually installed — do not leave an unpinned requirement.

**`.gitignore`**
```
.env
__pycache__/
*.pyc
.venv/
venv/
transcripts/raw/
```

**`.env.example`**
```
# At least one key required. Add up to six to spread free-tier quota.
GEMINI_API_KEY_1=
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
GEMINI_API_KEY_4=
GEMINI_API_KEY_5=
GEMINI_API_KEY_6=
```

→ **commit:** `chore: scaffold repo, pin deps, add env template`

### Step 2 — `src/config.py`

Single source of truth for tunables. No logic here beyond reading env.

- `MODEL_NAME = "gemini-3.5-flash-lite"`
- `MAX_KEYS = 6`, `KEY_ENV_PREFIX = "GEMINI_API_KEY_"`
- `MIN_TURNS = 5`, `MAX_TURNS = 7`
- `DIFFICULTY_MIN = 1`, `DIFFICULTY_MAX = 5`, `DIFFICULTY_START = 3`
- Generation defaults: `TEMPERATURE_QUESTION = 0.8` (question variety), `TEMPERATURE_JUDGMENT = 0.2` (evaluator and controller need stability), `TEMPERATURE_COACH = 0.5`
- `RATE_LIMIT_COOLDOWN_SECONDS = 60` — how long a key is benched after a 429
- `load_api_keys()` returning the non-empty keys in order, raising a clear error naming `.env.example` if none are set.

→ **commit:** `feat: add central config with model, turn bounds, difficulty scale`

### Step 3 — `src/llm_client.py`

The reliability layer. Everything else calls this and nothing else touches the Gemini SDK.

Implement `GeminiClient`:

- Constructor takes the key list, builds one `genai.Client(api_key=k)` per key, keeps a rotation index and a per-key `benched_until` timestamp.
- `_next_client()` — round-robin from the current index, skipping keys whose cooldown has not expired; if every key is benched, sleep until the earliest expiry rather than failing.
- `generate(system_prompt, user_content, temperature) -> str` — plain text.
- `generate_json(system_prompt, user_content, response_schema, temperature) -> dict` — passes `response_mime_type="application/json"` and `response_schema` in the generation config so the evaluator and controller get schema-conformant output from the API instead of relying on the prompt alone. Still wrap `json.loads` in a try/except and retry once with a repair instruction, because schema mode is a strong constraint but not a guarantee.
- Error handling: catch the SDK's rate-limit/quota error (429 / `RESOURCE_EXHAUSTED`), bench that key for `RATE_LIMIT_COOLDOWN_SECONDS`, advance to the next key, and retry. Cap total attempts at `2 * len(keys)`; on transient 5xx use exponential backoff (1s, 2s, 4s). Let genuine errors (bad request, invalid key) raise immediately with the key index masked in the message — never print a key.

Comment only the non-obvious parts: why keys are benched rather than dropped, and why judgment calls use low temperature.

→ **commit:** `feat: gemini client with 6-key round-robin rotation and 429 fallback`

### Step 4 — `src/prompt_loader.py`

`load_prompt(name: str) -> str` resolves `prompts/{name}.md` relative to the repo root, reads UTF-8, caches in a module-level dict. Raises a clear error if the file is missing. Ten lines, no cleverness.

→ **commit:** `feat: load agent prompts from prompts/ directory`

### Step 5 — `src/state.py`

Dataclasses only, no behaviour beyond small serializers.

- `CandidateProfile`: `target_role: str`, `background: str | None`, `focus_area: Literal["behavioral","technical","case","mixed"]`
- `Evaluation`: `scores: dict[str, int]`, `answer_type: str`, `strengths: list[str]`, `gaps: list[str]`, `missing_elements: list[str]`, `overall: float`, `rationale: str`
- `ControlDecision`: `action: str`, `rationale: str`, `next_difficulty: int`, `directive: str`, `topic: str`
- `Turn`: `index`, `question`, `answer`, `difficulty`, `evaluation: Evaluation | None`, `decision: ControlDecision | None`
- `SessionState`: `profile`, `turns: list[Turn]`, `difficulty: int`, `covered_topics: list[str]`, plus `transcript_text()` (question/answer pairs as readable text for the Coach) and `to_dict()` for the JSON session log.

→ **commit:** `feat: add session state dataclasses`

### Step 6 — The four prompt files

Write these before the agent classes — the agent code should be a thin shell around a prompt that already carries the thinking. Each prompt gets: role and scope, persona rules, what it receives, what it must output, and explicit handling of messy input.

**`prompts/interviewer.md`**
- Persona: a working practitioner interviewing for `{target_role}`, not a chatbot. Warm but not effusive; never coaches, never evaluates, never reveals scores or the controller's reasoning.
- Receives: role, background snippet, focus area, current difficulty (1–5 with a described meaning for each level), the directive from the Adaptive Controller, and the last 2–3 Q/A pairs for continuity.
- Rules: ask exactly one question; ≤ 3 sentences; no numbered sub-questions. When the directive is `probe_deeper`, reference something the candidate actually said rather than restating the question. Never repeat a covered topic unless probing it. Calibrate wording to the focus area — behavioral gets STAR-shaped situational prompts, technical gets concrete problems, case gets a scenario with constraints, mixed alternates.
- Messiness: if the last answer was off-topic, redirect once with a single clarifying sentence before the question. If the candidate said "I don't know", do not repeat the same question — offer a scaffolded, easier entry into the same area.
- Output: the question text only. No preamble, no labels, no markdown.

**`prompts/evaluator.md`**
- Role: a calibrated assessor. Judges only the answer given, never the person; does not write feedback for the candidate (that is the Coach's job) and never sees the Coach's output.
- Dimensions, each scored 1–5 with an anchored rubric written out in the prompt:
  `relevance` (answered what was asked), `specificity` (concrete detail, real examples, numbers), `depth` (reasoning beyond surface level), `structure` (organized and followable), `role_fit` (signal for the target role at the stated difficulty).
- `answer_type` classification, and this is what drives adaptation: `substantive` | `partial` | `vague` | `off_topic` | `non_answer` | `deflection`.
- Explicit calibration instructions: 3 is a competent baseline answer, not a failure; reserve 5 for answers with concrete evidence and clear reasoning; do not reward length or confident tone; partial correctness gets partial credit and the correct part is named in `strengths`.
- Messiness: `"I don't know"` is `non_answer` — score honestly low but note in `rationale` whether the candidate handled the gap gracefully (that is real signal). Off-topic answers score `relevance` 1 but other dimensions are still assessed on what was said.
- Output: JSON only, matching the schema passed via `response_schema`. Show the exact shape in the prompt as well.

**`prompts/adaptive_controller.md`**
- Role: the orchestration brain. It never speaks to the candidate — it writes instructions for the Interviewer. Say this in the prompt explicitly; it keeps the persona from leaking into questions.
- Receives: profile, current difficulty, the full sequence of (topic, answer_type, overall score) so far, the latest full evaluation, turn index, and `MIN_TURNS`/`MAX_TURNS`.
- Decides `action` ∈ `probe_deeper` | `move_on` | `switch_topic` | `raise_difficulty` | `ease_difficulty` | `wrap_up`, with a written policy:
  - score ≥ 4 and `substantive` → move on and raise difficulty (do not grind a topic the candidate has proven)
  - score ≤ 2 or `vague`/`partial` → probe deeper once on the specific missing element; if the same topic has already been probed twice, switch topic instead of a third probe
  - `non_answer` or `deflection` → ease difficulty and switch topic; the interview should stay productive, not punitive
  - `off_topic` → redirect on the same topic, difficulty unchanged
  - turn ≥ `MIN_TURNS` and coverage is adequate, or turn == `MAX_TURNS` → `wrap_up`
- Must emit a `directive`: one imperative sentence the Interviewer can act on, naming the specific thing to pursue (e.g. "Press for the actual metric they moved and how they measured it").
- Output: JSON only, schema-constrained.

**`prompts/coach.md`**
- Role: a candid, useful coach writing after the interview. Addresses the candidate as "you". Encouraging but never inflates — a weak interview is described as weak, kindly and concretely.
- Receives: profile, full transcript, every evaluation, the difficulty trajectory.
- Output: markdown with fixed sections — `## Overall Read` (3–4 sentences plus a readiness signal), `## Strengths` (2–4 bullets, each citing something the candidate actually said), `## Gaps` (2–4 bullets, each naming the specific moment it showed up), `## Dimension Scores` (a table averaging each dimension across turns), `## Practice Plan` (3–5 concrete actions — a drill, a rewrite of a specific answer, a topic to study — not generic advice like "practice more").
- Rules: quote or paraphrase the candidate's own words at least twice; no invented facts; if the interview was short or evasive, say the sample was thin rather than over-reading it.

→ **commit:** `feat: add system prompts for all four agents`

### Step 7 — `src/agents/base.py` and the four agent classes

`base.py`: `Agent` holds `client: GeminiClient` and `prompt_name: str`, loads its prompt lazily via `prompt_loader`, exposes `system_prompt` property. Subclasses implement `run(...)` with their own signature — deliberately not a single forced interface, because these agents genuinely differ in inputs and outputs.

- **`interviewer.py`** — `ask(state, decision) -> str`. Builds a compact context block (profile, difficulty with its meaning, directive, last 2–3 Q/A pairs), calls `generate()` at `TEMPERATURE_QUESTION`, strips stray quotes/labels from the returned line.
- **`evaluator.py`** — `evaluate(question, answer, profile, difficulty) -> Evaluation`. Defines `EVALUATION_SCHEMA` and calls `generate_json()` at `TEMPERATURE_JUDGMENT`. Computes `overall` as the mean of the five dimension scores in Python, not in the prompt — LLMs are unreliable at arithmetic and this number drives control flow.
- **`adaptive_controller.py`** — `decide(state, evaluation, turn_index) -> ControlDecision`. Defines `CONTROL_SCHEMA`, calls `generate_json()` at `TEMPERATURE_JUDGMENT`. Clamps `next_difficulty` to `[DIFFICULTY_MIN, DIFFICULTY_MAX]` in code, and force-overrides `action` to `wrap_up` when `turn_index >= MAX_TURNS` — hard limits belong in code, not in a prompt.
- **`coach.py`** — `summarize(state) -> str`. Assembles transcript plus all evaluations, calls `generate()` at `TEMPERATURE_COACH`, returns markdown.

→ **commit:** `feat: implement interviewer, evaluator, controller, and coach agents`

### Step 8 — `src/orchestrator.py`

`InterviewOrchestrator` owns the loop and is the file a reviewer will read to understand the system. Keep it readable.

```
seed:  controller produces an opening ControlDecision from the profile alone
       (no evaluation yet) — difficulty = DIFFICULTY_START, action = "move_on",
       directive derived from role + focus area

loop (turn = 1 .. MAX_TURNS):
    question = interviewer.ask(state, decision)
    answer   = yield to the CLI for input
    eval     = evaluator.evaluate(question, answer, profile, difficulty)
    decision = controller.decide(state, eval, turn)
    apply decision: state.difficulty = decision.next_difficulty
                    record topic in state.covered_topics
    record the Turn
    if decision.action == "wrap_up" and turn >= MIN_TURNS: break

after loop: report = coach.summarize(state)
```

Expose it as a generator or via callbacks so `cli.py` handles all I/O and the orchestrator handles none — that separation is what lets `scripts/simulate_candidate.py` reuse the exact same loop with a scripted answerer. Do not put `input()` or `print()` in this file.

Guard the empty-answer case in code: if the candidate submits an empty string, re-prompt once at the CLI layer rather than sending it to the Evaluator.

→ **commit:** `feat: orchestration loop sequencing the four agents`

### Step 9 — `src/cli.py` and `main.py`

`cli.py`:
- Intake: target role (required, free text), background snippet (optional, blank to skip), focus area (numbered menu 1–4, default `mixed`).
- Header printing the role, focus, and planned turn range so the candidate knows the shape of the session.
- Per turn: print `Question N/7`, the question, then a blocking `Your answer: ` prompt. Accept multi-line input terminated by a blank line — real interview answers are longer than one line.
- `--debug` flag: after each answer, print the evaluation JSON and the controller's action and rationale. Off by default so the candidate is not shown their scores mid-interview, which would change how they answer.
- After the loop: print the Coach's markdown, then write the full transcript to `transcripts/raw/session_<timestamp>.md` and the structured log to `transcripts/raw/session_<timestamp>.json`.
- Handle `KeyboardInterrupt` gracefully: if at least two turns are complete, still run the Coach on the partial session; otherwise exit cleanly.

`main.py`: `load_dotenv()`, `load_api_keys()`, build `GeminiClient`, build the four agents, build the orchestrator, call `cli.run()`. Argparse for `--debug`. Keep under 40 lines.

→ **commit:** `feat: CLI interface and entry point`

### Step 10 — `scripts/simulate_candidate.py`

Runs the same orchestrator with an LLM playing the candidate, so the three example transcripts are reproducible and produced by the real system rather than written by hand.

- Three personas as constants: `STRONG` (specific, metric-driven, structured), `WEAK` (vague, generic, no examples), `EVASIVE` (answers off-topic twice, says "I don't know" once, then gives one thin answer).
- Each persona is a system prompt for a separate `generate()` call that sees only the question and its own prior answers — never the evaluations.
- `python scripts/simulate_candidate.py --persona strong --role "Product Manager" --focus mixed --out transcripts/strong_candidate.md`
- Output format matches what a real CLI run produces, plus a one-line header noting the answers came from a simulated persona. Be upfront about this in the README rather than passing simulated runs off as human ones.

→ **commit:** `feat: candidate simulator for reproducible example transcripts`

### Step 11 — Generate the three transcripts

Run the simulator three times and commit the outputs:

1. `--persona strong --role "Product Manager" --focus mixed` → `transcripts/strong_candidate.md`
2. `--persona weak --role "Data Analyst" --focus technical` → `transcripts/weak_candidate.md`
3. `--persona evasive --role "Frontend Intern" --focus mixed` → `transcripts/edge_case_evasive.md`

Read each transcript afterwards and confirm the adaptive behaviour is actually visible — difficulty rising in the strong run, repeated probing then a topic switch in the weak run, redirection and easing in the evasive run. If it is not visible, the controller prompt policy needs tightening; fix the prompt and regenerate rather than editing the transcript by hand.

Each transcript file should show, per turn: the question, the answer, the evaluation JSON, and the controller's action + rationale — the debug view is what demonstrates the architecture to a reviewer.

→ **commit:** `docs: add three example interview transcripts`

### Step 12 — `README.md`

Write it last, from the finished code. Sections, in order:

1. **What this is** — two or three sentences. What the system does and what problem it solves.
2. **Setup** — Python 3.11+, `python -m venv .venv`, activate, `pip install -r requirements.txt`, `cp .env.example .env`, where to get free Gemini keys, note that one key is enough and up to six spreads free-tier quota.
3. **Run** — `python main.py`, and `python main.py --debug` to see evaluator and controller output live.
4. **Architecture** — an ASCII diagram, then a short paragraph per agent naming its input, output, and the one job it owns:

```
                        ┌──────────────────────┐
   candidate profile →  │     ORCHESTRATOR     │  ← turn bounds, difficulty state
                        └──────────┬───────────┘
                                   │  directive + difficulty
                                   ▼
                        ┌──────────────────────┐
                        │  INTERVIEWER AGENT   │  one question, candidate-facing
                        └──────────┬───────────┘
                                   │  question
                                   ▼
                            ┌─────────────┐
                            │  CANDIDATE  │  (CLI input)
                            └──────┬──────┘
                                   │  answer
                                   ▼
                        ┌──────────────────────┐
                        │   EVALUATOR AGENT    │  → JSON: 5 dimension scores,
                        └──────────┬───────────┘     answer_type, gaps
                                   │  evaluation
                                   ▼
                        ┌──────────────────────┐
                        │ ADAPTIVE CONTROLLER  │  → JSON: probe / move on /
                        │       AGENT          │     switch / ±difficulty / wrap
                        └──────────┬───────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              │ loop back to Interviewer (turns 1–7)    │
              └────────────────────┬────────────────────┘
                                   │  on wrap_up
                                   ▼
                        ┌──────────────────────┐
                        │     COACH AGENT      │  → markdown: strengths, gaps,
                        └──────────────────────┘     practice plan
```

5. **Why these are four agents and not four chained calls** — the strongest section for the reviewer. Make the concrete argument: the Interviewer never sees scores (so it cannot leak judgment into questions and cannot self-grade); the Evaluator never sees the Controller's policy (so scoring stays independent of what the system wants to do next); the Controller never produces candidate-facing text (it writes directives, not questions); the Coach sees everything but acts only once. Information is deliberately withheld between agents, control flow branches on the Controller's decision rather than running a fixed pipeline, and the same agent can be invoked a variable number of times per session.
6. **Key design decisions and tradeoffs** — one short paragraph each:
   - Flash-Lite over a larger model: latency matters more than depth for an interview loop, and free-tier quota is the binding constraint. Tradeoff: evaluator calibration is noisier, mitigated with anchored rubrics and low temperature.
   - Six-key round-robin: free-tier RPM is the real failure mode for a multi-agent system making 3+ calls per turn. Benching a rate-limited key beats failing the session.
   - Schema-constrained JSON over prompt-only JSON: fewer parse failures; still defended with a repair retry.
   - `overall` averaged in Python, and turn caps enforced in code: control flow should not depend on an LLM doing arithmetic or counting.
   - Prompts as separate files: they are the actual product surface here and are meant to be iterated on without touching Python.
   - Scores hidden from the candidate during the interview: showing them mid-session changes answering behaviour.
7. **Scope** — state plainly that RAG/web grounding, a web UI, deployment, and a demo video were left out; the assignment marks grounding optional and a CLI sufficient, and the effort went into the adaptation logic and prompt quality instead.
8. **Example transcripts** — link the three files with a one-line description of what each demonstrates.
9. **Known limitations** — 2–4 honest bullets (e.g. evaluator variance run-to-run, no persistence across sessions, no domain grounding so technical questions stay generalist).

Write in plain declarative prose. No "In today's fast-paced world", no emoji headers, no marketing tone.

→ **commit:** `docs: README with architecture, design decisions, and run instructions`

### Step 13 — Verification pass

Before the final commit, verify by running, not by reading:

1. `pip install -r requirements.txt` in a clean venv succeeds with the pinned versions.
2. `python main.py` with a single key in `.env` completes a full 5–7 turn interview and prints the Coach report.
3. `python main.py --debug` shows valid evaluation JSON and a controller action every turn.
4. Force a rotation test: put an invalid key in slot 1 and a valid one in slot 2, confirm the client falls through without crashing and never prints key material.
5. `grep -r "GEMINI_API_KEY" --include="*.py"` returns only `config.py`.
6. `git status` shows `.env` untracked and ignored.
7. Answer one question with an empty string, one with `"I don't know"`, and one with something off-topic — confirm the system handles all three without crashing and that the controller reacts differently to each.

Fix anything that fails, then:

→ **commit:** `fix: verification pass across rotation, edge cases, and clean install`

---

## 4. Git workflow

Run at the very start, before Step 1's files are written:

```bash
cd ai-mock-interview-coach
git init
git branch -M main
# create .gitignore first, before any git add, so .env can never be staged
```

Commit sequence — one per build step, in order:

| Step | Commit message |
|---|---|
| 1 | `chore: scaffold repo, pin deps, add env template` |
| 2 | `feat: add central config with model, turn bounds, difficulty scale` |
| 3 | `feat: gemini client with 6-key round-robin rotation and 429 fallback` |
| 4 | `feat: load agent prompts from prompts/ directory` |
| 5 | `feat: add session state dataclasses` |
| 6 | `feat: add system prompts for all four agents` |
| 7 | `feat: implement interviewer, evaluator, controller, and coach agents` |
| 8 | `feat: orchestration loop sequencing the four agents` |
| 9 | `feat: CLI interface and entry point` |
| 10 | `feat: candidate simulator for reproducible example transcripts` |
| 11 | `docs: add three example interview transcripts` |
| 12 | `docs: README with architecture, design decisions, and run instructions` |
| 13 | `fix: verification pass across rotation, edge cases, and clean install` |

Do not squash these into one commit — the commit history is part of what a reviewer reads.

Publish (GitHub CLI, preferred):

```bash
gh repo create ai-mock-interview-coach --public --source=. --remote=origin --push
```

Without `gh` — create the empty repo in the GitHub UI first (no README, no .gitignore), then:

```bash
git remote add origin https://github.com/<username>/ai-mock-interview-coach.git
git push -u origin main
```

Final check after pushing: open the repo on GitHub and confirm `.env` is absent and `.env.example` is present.

---

## 5. Requirement → implementation checklist

| Assignment requirement | Where it is satisfied |
|---|---|
| ~5–7 turn interview | `config.MIN_TURNS=5`, `MAX_TURNS=7`, enforced in `orchestrator.py` |
| Intelligent follow-ups, not a fixed list | Every question generated by `agents/interviewer.py` from the Controller's directive; no question bank exists in the repo |
| Adapt — probe deeper on weak answers | Controller `probe_deeper` action, triggered by score ≤ 2 or `vague`/`partial` answer_type |
| Adapt — move on from strong answers | Controller `move_on` + `raise_difficulty`, triggered by score ≥ 4 and `substantive` |
| Adapt — calibrate difficulty | `SessionState.difficulty` 1–5, updated each turn from `ControlDecision.next_difficulty`, clamped in code |
| Evaluate on multiple dimensions | `agents/evaluator.py` — relevance, specificity, depth, structure, role_fit, each 1–5 with anchored rubrics |
| Coach — structured final feedback | `agents/coach.py` + `prompts/coach.md` — fixed markdown sections: Overall Read, Strengths, Gaps, Dimension Scores, Practice Plan |
| ≥ 3 genuinely distinct agents | Four agents in `src/agents/`, each with its own prompt, inputs, output type, and invocation pattern; justified in README §5 |
| Orchestration logic shown | `src/orchestrator.py`, plus the ASCII diagram in README §4 |
| Thoughtful system prompt per agent | `prompts/interviewer.md`, `adaptive_controller.md`, `evaluator.md`, `coach.md` |
| Structured outputs — JSON for evaluator | `EVALUATION_SCHEMA` via `generate_json()` with `response_schema`, parsed into the `Evaluation` dataclass |
| Structured outputs — markdown for coach | `agents/coach.py` returns markdown; section structure fixed in the prompt |
| Handling vague / off-topic / partial / "I don't know" | `answer_type` enum in the Evaluator prompt; per-type branches in the Controller policy; redirect and scaffold rules in the Interviewer prompt; verified in Step 13.7 and in `transcripts/edge_case_evasive.md` |
| Interface — CLI acceptable | `src/cli.py`, `main.py`, `input()`-based |
| Grounding (optional) | Deliberately out of scope — stated with reasoning in README §7 |
| Modular, readable source | `src/` split into config / client / state / agents / orchestrator / cli, one responsibility each |
| `requirements.txt` | Present, versions pinned |
| `prompts/` folder, one file per agent | Present, four files, loaded at runtime by `prompt_loader.py` |
| README — setup/run instructions | README §2 and §3 |
| README — architecture overview | README §4 and §5 |
| README — design decisions / tradeoffs | README §6 and §9 |
| README — 3 example transcripts (strong / weak / edge case) | `transcripts/strong_candidate.md`, `weak_candidate.md`, `edge_case_evasive.md`, linked from README §8 |
| Gemini free tier, current flash-lite model | `config.MODEL_NAME = "gemini-3.5-flash-lite"` |
| 6-key rotation with 429 fallback | `src/llm_client.py`, keys loaded from `.env` as `GEMINI_API_KEY_1..6` |
