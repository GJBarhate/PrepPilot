import json

from ..config import TEMPERATURE_COACH
from ..prompt_loader import render_prompt
from ..state import SessionState
from .base import Agent


class CoachAgent(Agent):
    def __init__(self, client, prompt_name: str = "coach"):
        super().__init__(client, prompt_name)

    def summarize(self, state: SessionState) -> str:
        evals = []
        for t in state.turns:
            if t.evaluation:
                evals.append({
                    "turn": t.index,
                    "question": t.question,
                    "answer_excerpt": t.answer[:200],
                    "scores": t.evaluation.scores,
                    "answer_type": t.evaluation.answer_type,
                    "strengths": t.evaluation.strengths,
                    "gaps": t.evaluation.gaps,
                })

        dim_names = ["relevance", "specificity", "depth", "structure", "role_fit"]
        dim_averages = {}
        for dim in dim_names:
            values = [
                t.evaluation.scores.get(dim, 0)
                for t in state.turns
                if t.evaluation
            ]
            dim_averages[dim] = round(sum(values) / len(values), 1) if values else 0

        difficulties = [t.difficulty for t in state.turns]

        prompt = render_prompt(
            self.system_prompt,
            target_role=state.profile.target_role,
            background=state.profile.background or "Not provided",
            focus_area=state.profile.focus_area,
        )

        user_content = (
            f"## Full Transcript\n{state.transcript_text()}\n\n"
            f"## Evaluations\n{json.dumps(evals, indent=2)}\n\n"
            f"## Dimension Averages\n{json.dumps(dim_averages, indent=2)}\n\n"
            f"## Difficulty Trajectory\n{difficulties}\n\n"
            f"Write the coaching feedback report."
        )

        return self._client.generate(prompt, user_content, TEMPERATURE_COACH)
