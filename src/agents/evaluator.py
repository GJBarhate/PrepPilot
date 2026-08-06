from ..config import TEMPERATURE_JUDGMENT
from ..prompt_loader import render_prompt
from ..state import Evaluation
from .base import Agent

EVALUATION_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "properties": {
                "relevance": {"type": "integer"},
                "specificity": {"type": "integer"},
                "depth": {"type": "integer"},
                "structure": {"type": "integer"},
                "role_fit": {"type": "integer"},
            },
            "required": ["relevance", "specificity", "depth", "structure", "role_fit"],
        },
        "answer_type": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string"}},
        "missing_elements": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "required": ["scores", "answer_type", "strengths", "gaps", "missing_elements", "rationale"],
}


class EvaluatorAgent(Agent):
    def __init__(self, client, prompt_name: str = "evaluator"):
        super().__init__(client, prompt_name)

    def evaluate(self, question: str, answer: str, profile, difficulty: int) -> Evaluation:
        prompt = render_prompt(
            self.system_prompt,
            target_role=profile.target_role,
            background=profile.background or "Not provided",
            focus_area=profile.focus_area,
            difficulty=str(difficulty),
            question=question,
            answer=answer,
        )

        user_content = (
            f"Question: {question}\n\n"
            f"Candidate's answer: {answer}\n\n"
            f"Role: {profile.target_role} | Difficulty: {difficulty}/5 | Focus: {profile.focus_area}\n"
            f"Evaluate this answer."
        )

        data = self._client.generate_json(
            prompt, user_content, EVALUATION_SCHEMA, TEMPERATURE_JUDGMENT
        )

        scores = data["scores"]
        overall = sum(scores.values()) / len(scores)

        return Evaluation(
            scores=scores,
            answer_type=data["answer_type"],
            strengths=data.get("strengths", []),
            gaps=data.get("gaps", []),
            missing_elements=data.get("missing_elements", []),
            overall=round(overall, 2),
            rationale=data.get("rationale", ""),
        )
