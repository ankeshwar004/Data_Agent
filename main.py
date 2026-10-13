from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from agents.data_agent import build_data_agent_graph
from database.connection import db_connection


logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the data agent."""
    parser = argparse.ArgumentParser(
        description="Ask the financial data agent a question."
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="The question to answer. If omitted, the question is read from stdin.",
    )
    return parser.parse_args(argv)


def run(question: str) -> str:
    """Run the data agent for a question and return its final answer."""
    if not question.strip():
        raise ValueError("A non-empty question is required.")

    graph = build_data_agent_graph()
    result = graph.invoke({"user_query": question.strip()})
    answer = result.get("final_answer", "")

    if not answer.strip():
        raise RuntimeError("The data agent completed without producing an answer.")

    return answer


def main(argv: Sequence[str] | None = None) -> int:
    """Initialize dependencies, run the agent, and clean up resources."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)
    question = args.question or sys.stdin.readline().strip()
    if not question.strip():
        logger.error("A non-empty question is required.")
        return 1

    database_started = False
    try:
        logger.info("Starting data agent.")
        db_connection.init_db()
        database_started = True
        print(run(question))
        return 0
    except (RuntimeError, ValueError) as error:
        logger.error("%s", error)
        return 1
    finally:
        if database_started:
            db_connection.close_db()


if __name__ == "__main__":
    raise SystemExit(main())