"""Explainable candidate-pair features for ambiguous settlement evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
import math
import re
from typing import Mapping

from .data import EvaluationPair
from .domain import BankLine, Direction, Settlement

TOKEN_RE = re.compile(r"[A-Z0-9]+")
FEATURE_NAMES = (
    "amount_similarity",
    "amount_exact",
    "date_similarity",
    "token_jaccard",
    "character_similarity",
    "identifier_fragment",
    "settlement_keyword",
    "credit_direction",
)


@dataclass(frozen=True, slots=True)
class PairFeatures:
    values: Mapping[str, float]

    def vector(self) -> list[float]:
        return [float(self.values[name]) for name in FEATURE_NAMES]


def normalize_reference(text: str) -> str:
    return " ".join(TOKEN_RE.findall(text.upper()))


def tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.upper()))


def compute_pair_features(settlement: Settlement, bank_line: BankLine) -> PairFeatures:
    return _features(
        settlement_amount=settlement.reported_amount_paise,
        bank_amount=bank_line.amount_paise,
        settlement_date=settlement.settled_on,
        bank_date=bank_line.booked_on,
        settlement_reference=f"SETTLEMENT {settlement.settlement_id} UTR {settlement.utr}",
        bank_reference=bank_line.reference,
        direction=bank_line.direction,
    )


def compute_evaluation_features(pair: EvaluationPair) -> PairFeatures:
    return _features(
        settlement_amount=pair.settlement_amount_paise,
        bank_amount=pair.bank_amount_paise,
        settlement_date=pair.settlement_date,
        bank_date=pair.bank_date,
        settlement_reference=pair.settlement_reference,
        bank_reference=pair.bank_reference,
        direction=pair.direction,
    )


def _features(
    *,
    settlement_amount: int,
    bank_amount: int,
    settlement_date: date,
    bank_date: date,
    settlement_reference: str,
    bank_reference: str,
    direction: Direction,
) -> PairFeatures:
    amount_delta = abs(settlement_amount - bank_amount)
    # Smoothly decays while remaining interpretable: 1 at exact equality,
    # approximately 0.37 at a 1% relative error.
    scale = max(250.0, settlement_amount * 0.01)
    amount_similarity = math.exp(-amount_delta / scale)
    days = abs((bank_date - settlement_date).days)
    date_similarity = math.exp(-days / 2.0)

    settlement_norm = normalize_reference(settlement_reference)
    bank_norm = normalize_reference(bank_reference)
    settlement_tokens = tokens(settlement_reference)
    bank_tokens = tokens(bank_reference)
    union = settlement_tokens | bank_tokens
    token_jaccard = len(settlement_tokens & bank_tokens) / len(union) if union else 0.0
    character_similarity = SequenceMatcher(None, settlement_norm, bank_norm).ratio()

    generic = {"SETTLEMENT", "STLMNT", "RAZOR", "RZP", "CREDIT", "NEFT", "UTR", "SET"}
    meaningful = [token for token in settlement_tokens if len(token) >= 4 and token not in generic]
    bank_meaningful = [token for token in bank_tokens if len(token) >= 4 and token not in generic]
    identifier_fragment = 0.0
    for token in meaningful:
        for candidate in bank_meaningful:
            match = SequenceMatcher(None, token, candidate).find_longest_match(0, len(token), 0, len(candidate))
            if match.size >= 4:
                # Eight shared identifier characters are treated as full evidence;
                # shorter fragments remain useful but cannot dominate by themselves.
                identifier_fragment = max(identifier_fragment, min(1.0, match.size / 8.0))

    settlement_keyword = float(any(token in bank_tokens for token in {"SETTLEMENT", "STLMNT", "SET", "RZP", "RAZOR"}))
    return PairFeatures(
        {
            "amount_similarity": float(amount_similarity),
            "amount_exact": float(amount_delta == 0),
            "date_similarity": float(date_similarity),
            "token_jaccard": float(token_jaccard),
            "character_similarity": float(character_similarity),
            "identifier_fragment": float(identifier_fragment),
            "settlement_keyword": settlement_keyword,
            "credit_direction": float(direction is Direction.CREDIT),
        }
    )
