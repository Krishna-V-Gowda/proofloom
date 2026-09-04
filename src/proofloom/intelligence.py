"""Local, inspectable ambiguity ranking.

The model ranks candidate evidence. It never mutates financial facts or grants
permission to close a settlement; deterministic policy owns that authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve
from sklearn.preprocessing import StandardScaler

from .data import EvaluationDataset, EvaluationPair, generate_evaluation_dataset
from .domain import BankLine, CandidateScore, Settlement
from .features import FEATURE_NAMES, compute_evaluation_features, compute_pair_features


class ModelUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class AmbiguityModel:
    scaler: StandardScaler
    classifier: LogisticRegression
    threshold: float
    seed: int
    model_version: str
    available: bool = True

    @classmethod
    def train(
        cls,
        dataset: EvaluationDataset,
        *,
        seed: int = 20260903,
        minimum_validation_precision: float = 0.985,
    ) -> "AmbiguityModel":
        groups = dataset.merchant_groups
        train_groups = set(groups[:16])
        validation_groups = set(groups[16:20])
        train_pairs = [pair for pair in dataset.pairs if pair.merchant_id in train_groups]
        validation_pairs = [pair for pair in dataset.pairs if pair.merchant_id in validation_groups]
        X_train, y_train = matrix(train_pairs)
        X_validation, y_validation = matrix(validation_pairs)

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        classifier = LogisticRegression(
            random_state=seed,
            class_weight="balanced",
            C=1.2,
            max_iter=1000,
            solver="lbfgs",
        )
        classifier.fit(X_train_scaled, y_train)
        probabilities = classifier.predict_proba(scaler.transform(X_validation))[:, 1]
        threshold = select_precision_threshold(
            y_validation,
            probabilities,
            minimum_precision=minimum_validation_precision,
        )
        version_payload = {
            "features": FEATURE_NAMES,
            "mean": scaler.mean_.round(10).tolist(),
            "scale": scaler.scale_.round(10).tolist(),
            "coef": classifier.coef_.round(10).tolist(),
            "intercept": classifier.intercept_.round(10).tolist(),
            "threshold": round(float(threshold), 12),
            "seed": seed,
        }
        digest = hashlib.sha256(json.dumps(version_payload, sort_keys=True).encode()).hexdigest()[:12]
        return cls(scaler, classifier, float(threshold), seed, f"pl-local-logit-{digest}")

    @classmethod
    def default(cls) -> "AmbiguityModel":
        return cls.train(generate_evaluation_dataset())

    def score(self, settlement: Settlement, bank_line: BankLine) -> CandidateScore:
        if not self.available:
            raise ModelUnavailable("ambiguity model is offline")
        features = compute_pair_features(settlement, bank_line)
        probability = float(self.classifier.predict_proba(self.scaler.transform([features.vector()]))[0, 1])
        return CandidateScore(bank_line.bank_line_id, probability, features.values, self.model_version)

    def score_evaluation_pairs(self, pairs: Sequence[EvaluationPair]) -> np.ndarray:
        if not self.available:
            raise ModelUnavailable("ambiguity model is offline")
        X, _ = matrix(pairs)
        return self.classifier.predict_proba(self.scaler.transform(X))[:, 1]


def matrix(pairs: Sequence[EvaluationPair]) -> tuple[np.ndarray, np.ndarray]:
    X = np.asarray([compute_evaluation_features(pair).vector() for pair in pairs], dtype=float)
    y = np.asarray([pair.label for pair in pairs], dtype=int)
    return X, y


def select_precision_threshold(labels: np.ndarray, probabilities: np.ndarray, *, minimum_precision: float) -> float:
    precision, recall, thresholds = precision_recall_curve(labels, probabilities)
    candidates: list[tuple[float, float, float]] = []
    for index, threshold in enumerate(thresholds):
        p = float(precision[index])
        r = float(recall[index])
        if p >= minimum_precision:
            candidates.append((r, p, float(threshold)))
    if candidates:
        # Maximum recall, then precision, then lowest threshold for stability.
        candidates.sort(key=lambda item: (item[0], item[1], -item[2]), reverse=True)
        return candidates[0][2]
    # Fail closed if the requested operating point is not observed.
    return 1.0
