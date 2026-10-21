"""
eval/gold.py
============
Utilities for computing gold answers directly from the database.

No LLM is involved here.  Every gold value is derived by executing the
hand-written SQL in cases.py against the live PostgreSQL instance.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from database.connection import db_connection
from eval.cases import PositiveCase


# ── Normalisation helpers ──────────────────────────────────────────────────────

_SUFFIX_MAP = {
    "trillion": 1e12,
    "t": 1e12,
    "billion": 1e9,
    "bn": 1e9,
    "b": 1e9,
    "million": 1e6,
    "mn": 1e6,
    "m": 1e6,
    "thousand": 1e3,
    "k": 1e3,
}

# Regex to pull a signed numeric value plus an optional unit suffix from prose.
# Handles: "$391.035 billion", "391,035,000,000", "–$2.7 B", "($1.2M)", etc.
_NUMBER_RE = re.compile(
    r"""
    [\$€£]?                         # optional currency symbol
    \s*
    \(?                             # optional opening paren (negative)
    [-–]?                           # optional minus / dash
    ([\d,]+(?:\.\d+)?)              # integer or decimal, with optional commas
    \)?                             # optional closing paren
    \s*
    (trillion|billion|million|thousand|bn|mn|[tTbBmMkK])?  # optional suffix
    \b
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_number_from_text(text: str) -> float | None:
    """
    Extract the first numeric value from a free-form text string.

    Handles billions/millions suffixes, comma-separated thousands, currency
    symbols, and parenthetical negatives.  Returns None if nothing is found.
    """
    text = text.strip().replace("\n", " ")

    match = _NUMBER_RE.search(text)
    if not match:
        return None

    num_str, suffix = match.group(1), match.group(2)
    num_str = num_str.replace(",", "")
    value = float(num_str)

    if suffix:
        multiplier = _SUFFIX_MAP.get(suffix.lower(), 1.0)
        value *= multiplier

    # Detect negativity:
    # 1. Explicit leading minus/dash before the digits (possibly preceded by $)
    prefix = text[: match.start()]
    explicit_minus = bool(re.search(r"[-–][\s$€£]*$", prefix))

    # 2. Parenthetical negative: the entire number chunk is wrapped in ( … )
    #    e.g. "($1.2M)" or "( 99B )"
    paren_negative = False
    start, end = match.start(), match.end()
    # Walk backward/forward past optional $ and whitespace
    l = prefix.rstrip()  # everything before the match
    r = text[end:].lstrip()
    if l.endswith("(") and (r.startswith(")") or r.startswith(")")):
        paren_negative = True

    negative = explicit_minus or paren_negative

    if negative and value > 0:
        value = -value

    return value


def normalize_db_value(raw: Any) -> float | None:
    """Convert a DB-returned value (Decimal, int, float, str) to float."""
    if raw is None:
        return None
    if isinstance(raw, Decimal):
        return float(raw)
    if isinstance(raw, (int, float)):
        return float(raw)
    # Fallback: try to parse string representation
    return parse_number_from_text(str(raw))


def values_match(gold: float | None, candidate: float | None, rel_tol: float = 0.02) -> bool:
    """
    Return True when *candidate* is within *rel_tol* (default 2%) of *gold*.

    A 2% tolerance absorbs minor rounding differences between FMP data and
    published SEC figures, and copes with the LLM writing "$114.3 B" vs the
    DB value of 114,301,000,000.
    """
    if gold is None or candidate is None:
        return False
    if gold == 0:
        return abs(candidate) < 1.0  # both effectively zero
    return abs(gold - candidate) / abs(gold) <= rel_tol


# ── Gold answer computation ────────────────────────────────────────────────────

def compute_gold_answer(case: PositiveCase) -> dict:
    """
    Execute *case.gold_sql* against the live DB and return a dict:

        {
            "raw_row":   dict | None,    # full first row returned
            "gold_value": float | None,  # normalised value from gold_column
            "available": bool,           # False if the DB has no data for this case
        }
    """
    try:
        with db_connection.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(case.gold_sql)
                row = cur.fetchone()

        if row is None:
            return {"raw_row": None, "gold_value": None, "available": False}

        raw = row.get(case.gold_column) if hasattr(row, "get") else row[case.gold_column]
        return {
            "raw_row": dict(row),
            "gold_value": normalize_db_value(raw),
            "available": True,
        }

    except Exception as exc:
        return {"raw_row": None, "gold_value": None, "available": False, "error": str(exc)}
