import argparse
import sys

from dotenv import load_dotenv

from src.config import load_api_keys
from src.llm_client import GeminiClient
from src.agents import InterviewerAgent, EvaluatorAgent, AdaptiveControllerAgent, CoachAgent
from src.orchestrator import InterviewOrchestrator
from src.cli import run


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="AI Mock Interview Coach")
    parser.add_argument("--debug", action="store_true", help="Show evaluation and controller output after each turn")
    args = parser.parse_args()

    try:
        keys = load_api_keys()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    client = GeminiClient(keys)

    interviewer = InterviewerAgent(client)
    evaluator = EvaluatorAgent(client)
    controller = AdaptiveControllerAgent(client)
    coach = CoachAgent(client)

    orchestrator = InterviewOrchestrator(interviewer, evaluator, controller, coach)

    run(orchestrator, debug=args.debug)


if __name__ == "__main__":
    main()
