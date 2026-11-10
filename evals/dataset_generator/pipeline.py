import json
import logging

from collections import defaultdict
from pathlib import Path

from config import OUTPUT_DIR
from evals.dataset_generator.fetcher import DatasetFetcher
from evals.dataset_generator.fact_extractor import extract_company_facts
from evals.dataset_generator.question_generator import QuestionGenerator
from evals.dataset_generator.validator import DatasetValidator


logger = logging.getLogger(__name__)

def run_pipeline():

    fetcher = DatasetFetcher()

    generator = QuestionGenerator()

    validator = DatasetValidator()

    all_facts = []
    all_questions = []

    # 1. Fetch company financial data.
    companies = fetcher.run()

    # 2. Extract atomic facts.
    for company in companies:

        facts = extract_company_facts(
            ticker=company["ticker"],
            company=company["company_name"],
            statements=company["statements"],
        )

        all_facts.extend(facts)

    logger.info(f"Extracted {len(all_facts)} facts")

    # 3. Save facts for reproducibility.
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    facts_path = OUTPUT_DIR / "facts.json"

    facts_path.write_text(
        json.dumps(
            all_facts,
            indent=2,
            default=str
        ),
        encoding="utf-8"
    )

    # 4. Group facts by company and statement.
    groups = defaultdict(list)

    for fact in all_facts:

        key = (fact["ticker"],fact["statement"])
        groups[key].append(fact)

    # 5. Generate questions.
    for key, facts in groups.items():

        try:
            questions = generator.generate(facts)

            all_questions.extend(questions)

            logger.info(
                f"Generated {len(questions)} "
                f"questions for {key[0]}"
            )

        except Exception as exc:

            logger.info(f"Generation failed for {key}: {exc}")

    # 6. Validate and assemble ground truth.
    accepted, rejected = validator.validate(
        all_questions,
        all_facts
    )

    # 7. Save final dataset.
    dataset = {
        "version": 1,
        "generation_method": "hybrid",
        "total_facts": len(all_facts),
        "generated_questions": len(all_questions),
        "accepted_questions": len(accepted),
        "rejected_questions": len(rejected),
        "cases": accepted
    }

    output_path = (
        OUTPUT_DIR / "evaluation_dataset.json"
    )

    output_path.write_text(
        json.dumps(
            dataset,
            indent=2,
            default=str
        ),
        encoding="utf-8"
    )

    rejected_path = (
        OUTPUT_DIR / "rejected.json"
    )
    
    rejected_path.write_text(
        json.dumps(
            rejected,
            indent=2,
            default=str
        ),
        encoding="utf-8"
    )

    logger.info("\nDataset generation complete")

    logger.info(f"Facts: {len(all_facts)}")
    logger.info(f"Generated: {len(all_questions)}")
    logger.info(f"Accepted: {len(accepted)}")
    logger.info(f"Rejected: {len(rejected)}")



if __name__ == "__main__":
    run_pipeline()