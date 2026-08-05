from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CandidateProfile:
    target_role: str
    background: str | None = None
    focus_area: Literal["behavioral", "technical", "case", "mixed"] = "mixed"

    def to_dict(self) -> dict:
        return {
            "target_role": self.target_role,
            "background": self.background,
            "focus_area": self.focus_area,
        }


@dataclass
class Evaluation:
    scores: dict[str, int]
    answer_type: str
    strengths: list[str]
    gaps: list[str]
    missing_elements: list[str]
    overall: float
    rationale: str

    def to_dict(self) -> dict:
        return {
            "scores": self.scores,
            "answer_type": self.answer_type,
            "strengths": self.strengths,
            "gaps": self.gaps,
            "missing_elements": self.missing_elements,
            "overall": round(self.overall, 2),
            "rationale": self.rationale,
        }


@dataclass
class ControlDecision:
    action: str
    rationale: str
    next_difficulty: int
    directive: str
    topic: str

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "rationale": self.rationale,
            "next_difficulty": self.next_difficulty,
            "directive": self.directive,
            "topic": self.topic,
        }


@dataclass
class Turn:
    index: int
    question: str
    answer: str
    difficulty: int
    evaluation: Evaluation | None = None
    decision: ControlDecision | None = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "question": self.question,
            "answer": self.answer,
            "difficulty": self.difficulty,
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "decision": self.decision.to_dict() if self.decision else None,
        }


@dataclass
class SessionState:
    profile: CandidateProfile
    turns: list[Turn] = field(default_factory=list)
    difficulty: int = 3
    covered_topics: list[str] = field(default_factory=list)

    def transcript_text(self) -> str:
        lines = []
        for t in self.turns:
            lines.append(f"Q{t.index}: {t.question}")
            lines.append(f"A{t.index}: {t.answer}")
            lines.append("")
        return "\n".join(lines)

    def history_summary(self) -> list[dict]:
        return [
            {
                "turn": t.index,
                "topic": t.decision.topic if t.decision else "unknown",
                "answer_type": t.evaluation.answer_type if t.evaluation else "unknown",
                "overall": t.evaluation.overall if t.evaluation else 0,
            }
            for t in self.turns
        ]

    def to_dict(self) -> dict:
        return {
            "profile": self.profile.to_dict(),
            "difficulty": self.difficulty,
            "covered_topics": self.covered_topics,
            "turns": [t.to_dict() for t in self.turns],
        }
