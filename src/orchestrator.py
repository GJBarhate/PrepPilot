from .config import MIN_TURNS, MAX_TURNS, DIFFICULTY_START
from .state import SessionState, CandidateProfile, Turn
from .agents.interviewer import InterviewerAgent
from .agents.evaluator import EvaluatorAgent
from .agents.adaptive_controller import AdaptiveControllerAgent
from .agents.coach import CoachAgent


class InterviewOrchestrator:
    def __init__(
        self,
        interviewer: InterviewerAgent,
        evaluator: EvaluatorAgent,
        controller: AdaptiveControllerAgent,
        coach: CoachAgent,
    ):
        self.interviewer = interviewer
        self.evaluator = evaluator
        self.controller = controller
        self.coach = coach

    def run(self, profile: CandidateProfile):
        state = SessionState(profile=profile, difficulty=DIFFICULTY_START)
        decision = self.controller.seed_decision(state)

        for turn_num in range(1, MAX_TURNS + 1):
            question = self.interviewer.ask(state, decision)

            answer = yield ("question", turn_num, question)

            evaluation = self.evaluator.evaluate(
                question, answer, profile, state.difficulty
            )

            decision = self.controller.decide(state, evaluation, turn_num)

            state.difficulty = decision.next_difficulty
            if decision.topic and decision.topic not in state.covered_topics:
                state.covered_topics.append(decision.topic)

            turn = Turn(
                index=turn_num,
                question=question,
                answer=answer,
                difficulty=state.difficulty,
                evaluation=evaluation,
                decision=decision,
            )
            state.turns.append(turn)

            yield ("turn_complete", turn_num, turn)

            if decision.action == "wrap_up" and turn_num >= MIN_TURNS:
                break

        report = self.coach.summarize(state)
        yield ("report", 0, report)
        yield ("state", 0, state)
