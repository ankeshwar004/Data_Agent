import json
import logging

from config import OUTPUT_DIR
from evals.dataset_generator.fetcher import DatasetFetcher
from evals.dataset_generator.fact_extractor import extract_company_facts
from evals.dataset_generator.evidence_builder import build_evidence
from evals.dataset_generator.question_generator import QuestionGenerator
from evals.dataset_generator.validator import DatasetValidator


logger = logging.getLogger(__name__)


def run_pipeline():
    generator = QuestionGenerator()
    validator = DatasetValidator()

    # 1. Fetch data and extract atomic facts (the source of truth).
    companies = DatasetFetcher().run()
    all_facts = [
        fact
        for company in companies
        for fact in extract_company_facts(company["ticker"], company["company_name"], company["statements"])
    ]

    logger.info("Extracted %s atomic facts", len(all_facts))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUTPUT_DIR / "facts.json").write_text(
        json.dumps(all_facts, indent=2, default=str),
        encoding="utf-8",
    )

    # 2. Build deterministic evidence units from compatible facts.
    all_evidence = build_evidence(all_facts)
    (OUTPUT_DIR / "evidence.json").write_text(
        json.dumps(all_evidence, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Built %s evidence items", len(all_evidence))

    # 3. Let the LLM generate multiple questions from evidence batches.
    all_questions = generator.generate(all_evidence)
    logger.info("Generated %s questions", len(all_questions))

    # 4. Validate each question and calculate its ground-truth answer in Python.
    accepted, rejected = validator.validate( all_questions, all_evidence, all_facts)

    dataset = {
        "version": 1,
        "generation_method": "evidence_based_hybrid",
        "total_facts": len(all_facts),
        "total_evidence": len(all_evidence),
        "generated_questions": len(all_questions),
        "accepted_questions": len(accepted),
        "rejected_questions": len(rejected),
        "cases": accepted,
    }
    (OUTPUT_DIR / "evaluation_dataset.json").write_text(
        json.dumps(dataset, indent=2, default=str),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "rejected.json").write_text(
        json.dumps(rejected, indent=2, default=str),
        encoding="utf-8",
    )

    logger.info(
        "Dataset generation complete: %s facts, %s evidence, %s generated, "
        "%s accepted, %s rejected",
        len(all_facts), len(all_evidence), len(all_questions), len(accepted), len(rejected),
    )


if __name__ == "__main__":
    run_pipeline()
