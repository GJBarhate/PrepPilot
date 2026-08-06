import json
import os
from datetime import datetime

from .config import MIN_TURNS, MAX_TURNS
from .state import CandidateProfile, SessionState
from .orchestrator import InterviewOrchestrator


FOCUS_OPTIONS = {
    "1": "behavioral",
    "2": "technical",
    "3": "case",
    "4": "mixed",
}


def get_multiline_input(prompt_text: str) -> str:
    print(prompt_text, end="")
    lines = []
    while True:
        line = input()
        if line == "":
            if lines:
                break
            continue
        lines.append(line)
    return "\n".join(lines)


def intake() -> CandidateProfile:
    print("\n" + "=" * 60)
    print("  AI MOCK INTERVIEW COACH")
    print("=" * 60 + "\n")

    role = ""
    while not role.strip():
        role = input("Target role (e.g., Product Manager, Software Engineer): ").strip()

    background = input("Brief background (optional, press Enter to skip): ").strip() or None

    print("\nFocus area:")
    print("  1. Behavioral")
    print("  2. Technical")
    print("  3. Case")
    print("  4. Mixed (default)")
    choice = input("Choose [1-4]: ").strip()
    focus = FOCUS_OPTIONS.get(choice, "mixed")

    return CandidateProfile(target_role=role, background=background, focus_area=focus)


def save_transcript(state: SessionState, report: str):
    raw_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "transcripts", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    md_lines = [
        f"# Mock Interview Transcript — {state.profile.target_role}",
        f"*Focus: {state.profile.focus_area} | Generated: {datetime.now().isoformat()}*\n",
    ]
    for t in state.turns:
        md_lines.append(f"## Turn {t.index} (Difficulty {t.difficulty}/5)")
        md_lines.append(f"**Question:** {t.question}\n")
        md_lines.append(f"**Answer:** {t.answer}\n")
        if t.evaluation:
            md_lines.append(f"**Evaluation:** `{json.dumps(t.evaluation.to_dict())}`\n")
        if t.decision:
            md_lines.append(f"**Controller:** action=`{t.decision.action}` | {t.decision.rationale}\n")
        md_lines.append("---\n")
    md_lines.append("## Coach Feedback\n")
    md_lines.append(report)

    with open(os.path.join(raw_dir, f"session_{ts}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    with open(os.path.join(raw_dir, f"session_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)

    print(f"\nTranscript saved to transcripts/raw/session_{ts}.md")


def run(orchestrator: InterviewOrchestrator, debug: bool = False):
    profile = intake()

    print(f"\n{'─' * 60}")
    print(f"Starting interview for: {profile.target_role}")
    print(f"Focus: {profile.focus_area} | Turns: {MIN_TURNS}–{MAX_TURNS}")
    print(f"{'─' * 60}\n")

    gen = orchestrator.run(profile)
    state = None
    report = None

    try:
        event = next(gen)
        while True:
            event_type, turn_num, data = event

            if event_type == "session_start":
                state = data
                event = next(gen)

            elif event_type == "question":
                print(f"\n{'━' * 50}")
                print(f"  Question {turn_num}/{MAX_TURNS}")
                print(f"{'━' * 50}")
                print(f"\n{data}\n")

                answer = ""
                while not answer.strip():
                    answer = get_multiline_input("Your answer (blank line to submit):\n")
                    if not answer.strip():
                        print("(Please provide an answer — press Enter on a blank line to submit.)")

                event = gen.send(answer)

            elif event_type == "turn_complete":
                turn = data
                if debug and turn.evaluation:
                    print(f"\n  [DEBUG] Evaluation: {json.dumps(turn.evaluation.to_dict(), indent=2)}")
                if debug and turn.decision:
                    print(f"  [DEBUG] Controller: action={turn.decision.action}, "
                          f"rationale={turn.decision.rationale}, "
                          f"next_difficulty={turn.decision.next_difficulty}")
                event = next(gen)

            elif event_type == "report":
                report = data
                print(f"\n{'═' * 60}")
                print("  INTERVIEW FEEDBACK")
                print(f"{'═' * 60}\n")
                print(report)
                event = next(gen)

            elif event_type == "state":
                state = data
                break

            else:
                event = next(gen)

    except KeyboardInterrupt:
        print("\n\nInterview interrupted.")
        if report is None:
            if state and len(state.turns) >= 2:
                print("Generating feedback from the turns you completed...\n")
                report = orchestrator.coach.summarize(state)
                print(report)
            else:
                print("Not enough turns for feedback. Exiting.")
                return

    if state and report:
        save_transcript(state, report)
