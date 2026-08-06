from ..config import TEMPERATURE_QUESTION
from ..prompt_loader import render_prompt
from ..state import SessionState, ControlDecision
from .base import Agent

DIFFICULTY_LABELS = {
    1: "Entry-level fundamentals",
    2: "Junior-level application",
    3: "Mid-level competence",
    4: "Senior-level complexity",
    5: "Staff/principal-level depth",
}


class InterviewerAgent(Agent):
    def __init__(self, client, prompt_name: str = "interviewer"):
        super().__init__(client, prompt_name)

    def ask(self, state: SessionState, decision: ControlDecision) -> str:
        recent = state.turns[-3:] if state.turns else []
        history_text = ""
        for t in recent:
            history_text += f"Q: {t.question}\nA: {t.answer}\n\n"
        if not history_text:
            history_text = "(This is the first question.)"

        prompt = render_prompt(
            self.system_prompt,
            target_role=state.profile.target_role,
            background=state.profile.background or "Not provided",
            focus_area=state.profile.focus_area,
            difficulty=str(state.difficulty),
            directive=decision.directive,
            recent_history=history_text,
        )

        user_content = (
            f"Current difficulty: {state.difficulty}/5 ({DIFFICULTY_LABELS.get(state.difficulty, '')})\n"
            f"Directive: {decision.directive}\n"
            f"Topic to cover: {decision.topic}\n"
            f"Focus area: {state.profile.focus_area}\n"
            f"Generate the next interview question."
        )

        result = self._client.generate(prompt, user_content, TEMPERATURE_QUESTION)
        result = result.strip().strip('"').strip("'")
        for prefix in ["Question:", "Q:", "**Question:**", "**Q:**"]:
            if result.startswith(prefix):
                result = result[len(prefix):].strip()
        return result
