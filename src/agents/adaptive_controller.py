import json

from ..config import TEMPERATURE_JUDGMENT, DIFFICULTY_MIN, DIFFICULTY_MAX, MIN_TURNS, MAX_TURNS
from ..prompt_loader import render_prompt
from ..state import SessionState, Evaluation, ControlDecision
from .base import Agent

CONTROL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "rationale": {"type": "string"},
        "next_difficulty": {"type": "integer"},
        "directive": {"type": "string"},
        "topic": {"type": "string"},
    },
    "required": ["action", "rationale", "next_difficulty", "directive", "topic"],
}


class AdaptiveControllerAgent(Agent):
    def __init__(self, client, prompt_name: str = "adaptive_controller"):
        super().__init__(client, prompt_name)

    def seed_decision(self, state: SessionState) -> ControlDecision:
        topic_map = {
            "behavioral": "past experience and situational judgment",
            "technical": "core technical skills and problem solving",
            "case": "analytical reasoning and case analysis",
            "mixed": "general competency and role readiness",
        }
        topic = topic_map.get(state.profile.focus_area, "general competency")
        return ControlDecision(
            action="move_on",
            rationale="Opening question — starting the interview at baseline difficulty.",
            next_difficulty=state.difficulty,
            directive=f"Ask an opening question to assess the candidate's background and readiness for the {state.profile.target_role} role, focusing on {topic}.",
            topic=topic,
        )

    def decide(self, state: SessionState, evaluation: Evaluation, turn_index: int) -> ControlDecision:
        if turn_index >= MAX_TURNS:
            return ControlDecision(
                action="wrap_up",
                rationale=f"Turn {turn_index} has reached MAX_TURNS ({MAX_TURNS}). Ending interview.",
                next_difficulty=state.difficulty,
                directive="Wrap up the interview with a closing remark.",
                topic=state.covered_topics[-1] if state.covered_topics else "general",
            )

        history = json.dumps(state.history_summary(), indent=2)
        eval_json = json.dumps(evaluation.to_dict(), indent=2)

        prompt = render_prompt(
            self.system_prompt,
            target_role=state.profile.target_role,
            background=state.profile.background or "Not provided",
            focus_area=state.profile.focus_area,
            difficulty=str(state.difficulty),
            turn_index=str(turn_index),
            min_turns=str(MIN_TURNS),
            max_turns=str(MAX_TURNS),
        )

        user_content = (
            f"Turn history:\n{history}\n\n"
            f"Latest evaluation:\n{eval_json}\n\n"
            f"Current turn: {turn_index} | Difficulty: {state.difficulty}/5\n"
            f"Covered topics: {', '.join(state.covered_topics) if state.covered_topics else 'none yet'}\n"
            f"Decide the next action."
        )

        data = self._client.generate_json(
            prompt, user_content, CONTROL_SCHEMA, TEMPERATURE_JUDGMENT
        )

        next_diff = max(DIFFICULTY_MIN, min(DIFFICULTY_MAX, data["next_difficulty"]))

        action = data["action"]
        if turn_index >= MAX_TURNS:
            action = "wrap_up"

        return ControlDecision(
            action=action,
            rationale=data["rationale"],
            next_difficulty=next_diff,
            directive=data["directive"],
            topic=data["topic"],
        )
