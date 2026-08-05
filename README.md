# AI Mock Interview Coach

A multi-agent system that conducts adaptive mock interviews using Google's Gemini API. Four specialized agents collaborate to interview a candidate, evaluate responses across multiple dimensions, adjust difficulty in real time, and deliver structured coaching feedback. The system runs entirely from the command line and requires only free-tier Gemini API keys.

## Setup

**Requirements:** Python 3.11+

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and paste at least one Gemini API key into `GEMINI_API_KEY_1`. Free keys are available at [Google AI Studio](https://aistudio.google.com/apikey). One key is enough to run; adding up to six spreads free-tier rate limits across keys so the multi-agent loop is less likely to hit quota mid-session.

## Run

Start an interactive interview:

```bash
python main.py
```

Show evaluator scores and controller decisions after each turn (useful for understanding the system's behavior):

```bash
python main.py --debug
```

The CLI prompts for a target role, optional background, and focus area (behavioral / technical / case / mixed), then conducts a 5-7 turn interview. Multi-line answers are supported — submit by pressing Enter on a blank line. After the final turn, the Coach agent prints a structured feedback report and the full transcript is saved to `transcripts/raw/`.

## Architecture

```
                        +----------------------+
   candidate profile -> |     ORCHESTRATOR     |  <- turn bounds, difficulty state
                        +----------+-----------+
                                   |  directive + difficulty
                                   v
                        +----------------------+
                        |  INTERVIEWER AGENT   |  one question, candidate-facing
                        +----------+-----------+
                                   |  question
                                   v
                            +-------------+
                            |  CANDIDATE  |  (CLI input)
                            +------+------+
                                   |  answer
                                   v
                        +----------------------+
                        |   EVALUATOR AGENT    |  -> JSON: 5 dimension scores,
                        +----------+-----------+     answer_type, gaps
                                   |  evaluation
                                   v
                        +----------------------+
                        | ADAPTIVE CONTROLLER  |  -> JSON: probe / move on /
                        |       AGENT          |     switch / +/-difficulty / wrap
                        +----------+-----------+
                                   |
              +--------------------+--------------------+
              | loop back to Interviewer (turns 1-7)    |
              +--------------------+--------------------+
                                   |  on wrap_up
                                   v
                        +----------------------+
                        |     COACH AGENT      |  -> markdown: strengths, gaps,
                        +----------------------+     practice plan
```

**Interviewer Agent** receives a directive from the controller and the recent conversation history. It generates exactly one interview question calibrated to the target role, focus area, and current difficulty level. It never evaluates, never coaches, and never reveals internal state.

**Evaluator Agent** scores each answer across five dimensions (relevance, specificity, depth, structure, role_fit) on a 1-5 scale with anchored rubrics. It classifies the answer type (substantive, partial, vague, off_topic, non_answer, deflection) which drives the controller's adaptation logic. Output is schema-constrained JSON.

**Adaptive Controller Agent** reads the evaluation and the full turn history, then decides what happens next: probe deeper on a weak answer, move on and raise difficulty after a strong one, switch topics after repeated probing, ease difficulty after a non-answer, or wrap up when coverage is sufficient. It writes a directive for the Interviewer but never produces candidate-facing text.

**Coach Agent** runs once after the interview ends. It receives the full transcript and all evaluations, then writes a structured markdown report with an overall read, cited strengths and gaps, averaged dimension scores, and a concrete practice plan.

## Why these are four agents and not four chained calls

The agent boundaries exist to enforce information asymmetry, not just code modularity.

The Interviewer never sees scores. This prevents it from leaking judgment into questions ("Since you struggled with...") or self-grading. The Evaluator never sees the Controller's policy, so scoring stays independent of what the system plans to do next — a vague answer scores the same whether the controller will probe or move on. The Controller never produces candidate-facing text; it writes directives, not questions, which prevents the orchestration logic from bleeding into the interview tone. The Coach sees everything but acts only once, after the interview ends, so its feedback cannot influence the candidate's subsequent answers.

Control flow branches on the Controller's decision rather than running a fixed pipeline. The same Interviewer agent is invoked a variable number of times per session (5-7), and the Controller can change direction at any turn. This is genuine orchestration, not sequential chaining.

## Key design decisions and tradeoffs

**Flash-Lite over a larger model.** Latency matters more than depth for an interview loop that makes 3+ LLM calls per turn, and free-tier quota is the binding constraint. The tradeoff is that evaluator calibration is noisier, which is mitigated with anchored rubrics in the prompt and low generation temperature (0.2).

**Six-key round-robin.** Free-tier RPM is the real failure mode for a multi-agent system making 3+ calls per turn. When a key hits a 429, it is benched for 60 seconds and the next key takes over. This keeps the session alive rather than failing. Keys are benched, not dropped, so they re-enter rotation after cooldown.

**Schema-constrained JSON.** The evaluator and controller use `response_mime_type="application/json"` with `response_schema` in the Gemini API config, so the model returns schema-conformant output. This produces far fewer parse failures than prompt-only JSON. A repair retry is still in place as a fallback.

**`overall` averaged in Python, turn caps enforced in code.** Control flow should not depend on an LLM doing arithmetic or counting. The overall score is the mean of five dimension scores computed in Python, and `wrap_up` is forced when `turn_index >= MAX_TURNS` regardless of what the controller says.

**Prompts as separate files.** The four prompt files in `prompts/` are the actual product surface — they carry the interview logic, rubrics, and persona rules. Keeping them as editable markdown files means they can be iterated without touching Python code.

**Scores hidden from the candidate during the interview.** Showing scores mid-session would change how the candidate answers. The `--debug` flag reveals them for development and review purposes.

## Scope

RAG/web grounding, a web UI, deployment infrastructure, Docker, and a demo video were deliberately left out. The assignment marks grounding as optional and a CLI as sufficient. The effort went into the adaptation logic, prompt quality, and the four-agent orchestration architecture instead.

## Example transcripts

These were generated by the `scripts/simulate_candidate.py` script, which runs the same orchestrator with an LLM playing the candidate. The answers are LLM-generated, not human-written — this is stated in each transcript.

- **[Strong candidate](transcripts/strong_candidate.md)** — A well-prepared Product Manager candidate giving specific, metric-driven answers. Shows the system raising difficulty and moving on efficiently, wrapping up at turn 5.
- **[Weak candidate](transcripts/weak_candidate.md)** — A vague Data Analyst candidate with no concrete examples. Shows repeated probing on weak answers, then topic switching after the same area is probed twice.
- **[Evasive candidate](transcripts/edge_case_evasive.md)** — A Frontend Intern candidate who gives off-topic answers, says "I don't know", then provides thin responses. Shows the system redirecting, easing difficulty, and handling non-answers gracefully.

## Known limitations

- **Evaluator variance.** Flash-Lite scores can vary 0.5-1.0 points between runs on the same answer. The anchored rubrics and low temperature reduce but do not eliminate this.
- **No persistence across sessions.** Each interview starts fresh. There is no memory of prior sessions or longitudinal tracking.
- **No domain grounding.** Technical questions stay generalist because the system has no access to domain-specific knowledge bases or documentation. A RAG layer would improve technical question quality.
- **Single-turn answer format.** The CLI accepts one answer per question. Real interviews involve back-and-forth clarification, which this system does not support.
