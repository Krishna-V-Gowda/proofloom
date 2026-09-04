"""Reproducible merchant-group evaluation for Proofloom's ambiguity ranker."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import csv
import json
from pathlib import Path
import platform
import random
import time
from typing import Any, Iterable, Sequence

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from .data import EvaluationDataset, EvaluationPair, generate_evaluation_dataset
from .features import compute_evaluation_features, normalize_reference
from .intelligence import AmbiguityModel


def run_evaluation(output_dir: str | Path, *, seed: int = 20260920, bootstrap_resamples: int = 500) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    dataset = generate_evaluation_dataset(seed)
    model = AmbiguityModel.train(dataset, seed=seed)
    test_groups = set(dataset.merchant_groups[20:24])
    test_pairs = [pair for pair in dataset.pairs if pair.merchant_id in test_groups]
    probabilities = model.score_evaluation_pairs(test_pairs)
    labels = np.asarray([pair.label for pair in test_pairs], dtype=int)
    predictions = probabilities >= model.threshold

    pair_metrics = {
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "pr_auc": float(average_precision_score(labels, probabilities)),
        "roc_auc": float(roc_auc_score(labels, probabilities)),
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "ece_10_bin": float(expected_calibration_error(labels, probabilities, bins=10)),
        "threshold": float(model.threshold),
        "records": len(test_pairs),
        "positives": int(labels.sum()),
    }

    validation_groups = set(dataset.merchant_groups[16:20])
    validation_pairs = [pair for pair in dataset.pairs if pair.merchant_id in validation_groups]
    validation_probabilities = model.score_evaluation_pairs(validation_pairs)
    validation_grouped = group_predictions(validation_pairs, validation_probabilities)
    operating_point = select_policy_operating_point(validation_grouped)

    grouped = group_predictions(test_pairs, probabilities)
    baseline = evaluate_policy(grouped, policy="deterministic")
    hybrid = evaluate_policy(
        grouped,
        policy="hybrid",
        threshold=operating_point["threshold"],
        minimum_margin=operating_point["minimum_margin"],
    )
    stress = evaluate_stress(
        grouped,
        threshold=operating_point["threshold"],
        minimum_margin=operating_point["minimum_margin"],
    )
    intervals = bootstrap_policy_delta(
        grouped,
        threshold=operating_point["threshold"],
        minimum_margin=operating_point["minimum_margin"],
        resamples=bootstrap_resamples,
        seed=seed + 99,
    )

    false_auto_cost = 2500
    manual_review_cost = 35
    for result in (baseline, hybrid):
        result["illustrative_operating_cost_inr"] = (
            result["false_auto_matches"] * false_auto_cost + result["review_queue"] * manual_review_cost
        )

    result: dict[str, Any] = {
        "evaluation_date": "2026-09-04",
        "dataset": {
            "type": "synthetic candidate-pair benchmark",
            "seed": seed,
            "merchant_groups": len(dataset.merchant_groups),
            "split": {"train": 16, "validation": 4, "test": 4},
            "test_settlements": len(grouped),
            "test_candidate_pairs": len(test_pairs),
            "candidates_per_settlement": 6,
            "separation": "merchant-specific identifiers do not cross train, validation and test groups",
        },
        "model": {
            "method": "standardized class-balanced logistic regression",
            "scope": "rank ambiguous settlement-bank candidates; deterministic policy owns financial authority",
            "pair_classification_threshold": float(model.threshold),
            "policy_operating_point": operating_point,
            "thresholds_selected_on": "validation merchant groups only",
            "version": model.model_version,
        },
        "pair_classifier_held_out": pair_metrics,
        "policy_comparison": {"deterministic_baseline": baseline, "proofloom_hybrid": hybrid},
        "merchant_bootstrap": intervals,
        "stress_test": stress,
        "economics": {
            "false_auto_match_cost_inr": false_auto_cost,
            "manual_review_cost_inr": manual_review_cost,
            "status": "illustrative sensitivity assumptions; not observed merchant costs or ROI",
        },
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "limitations": [
            "All records and labels are synthetic; live merchant generalization is not established.",
            "Labels are generated by the documented simulator rather than adjudicated by finance operators.",
            "The economic model is a sensitivity aid, not production ROI.",
            "Split-settlement search is verified in integration tests rather than the one-to-one pair benchmark.",
            "The stress set reweights difficult synthetic cases; it is not a field distribution estimate.",
        ],
    }
    (output / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_predictions(
        output / "predictions.csv",
        grouped,
        threshold=operating_point["threshold"],
        minimum_margin=operating_point["minimum_margin"],
    )
    write_markdown(output / "results.md", result)
    render_evaluation_figure(output / "evaluation-summary.png", result)
    render_evaluation_figure(output / "evaluation-summary.svg", result)
    return result


def group_predictions(pairs: Sequence[EvaluationPair], probabilities: Sequence[float]) -> list[dict[str, Any]]:
    by_settlement: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair, probability in zip(pairs, probabilities, strict=True):
        by_settlement[pair.settlement_id].append(
            {
                "pair": pair,
                "score": float(probability),
                "features": compute_evaluation_features(pair).values,
            }
        )
    result = []
    for settlement_id, candidates in sorted(by_settlement.items()):
        candidates.sort(key=lambda item: (-item["score"], item["pair"].bank_line_id))
        result.append(
            {
                "settlement_id": settlement_id,
                "merchant_id": candidates[0]["pair"].merchant_id,
                "difficulty": next(item["pair"].difficulty for item in candidates if item["pair"].label == 1),
                "candidates": candidates,
            }
        )
    return result


def evaluate_policy(
    groups: Sequence[dict[str, Any]],
    *,
    policy: str,
    threshold: float = 1.0,
    minimum_margin: float = 0.05,
) -> dict[str, Any]:
    auto = 0
    correct = 0
    false = 0
    difficulty_counts: dict[str, int] = defaultdict(int)
    for group in groups:
        candidates = group["candidates"]
        selected = None
        if policy == "deterministic":
            qualifying = [item for item in candidates if deterministic_exact(item["pair"])]
            if len(qualifying) == 1:
                selected = qualifying[0]
        elif policy == "hybrid":
            top = candidates[0]
            runner_up = candidates[1]["score"] if len(candidates) > 1 else 0.0
            pair = top["pair"]
            features = top["features"]
            # Financial policy remains deterministic. The model can only own a
            # candidate that is a credit, timely, near-exact in amount and
            # decisively above the validation-selected threshold.
            policy_safe = (
                pair.direction.value == "credit"
                and abs((pair.bank_date - pair.settlement_date).days) <= 3
                and abs(pair.bank_amount_paise - pair.settlement_amount_paise) <= 1
                and top["score"] >= threshold
                and top["score"] - runner_up >= minimum_margin
            )
            if policy_safe:
                selected = top
        else:
            raise ValueError(policy)
        if selected is not None:
            auto += 1
            difficulty_counts[group["difficulty"]] += 1
            if selected["pair"].label == 1:
                correct += 1
            else:
                false += 1
    total = len(groups)
    return {
        "settlements": total,
        "auto_matches": auto,
        "correct_auto_matches": correct,
        "false_auto_matches": false,
        "auto_match_precision": correct / auto if auto else 0.0,
        "straight_through_rate": auto / total if total else 0.0,
        "review_queue": total - auto,
        "auto_matches_by_true_difficulty": dict(sorted(difficulty_counts.items())),
    }



def select_policy_operating_point(groups: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Choose a validation-only operating point for policy automation.

    Candidate ranking metrics and financial automation are deliberately
    separated. The pair classifier uses a precision-oriented classification
    threshold; the policy then searches a small predeclared grid and requires
    zero false auto-matches on validation merchant groups. Exact amount,
    direction, booking-window and top-vs-runner-up margin checks remain hard
    deterministic gates.
    """
    thresholds = (0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 0.90)
    margins = (0.05, 0.08, 0.10, 0.12, 0.15, 0.20)
    candidates: list[tuple[int, float, float, dict[str, Any]]] = []
    for threshold in thresholds:
        for margin in margins:
            result = evaluate_policy(
                groups,
                policy="hybrid",
                threshold=threshold,
                minimum_margin=margin,
            )
            if result["auto_matches"] and result["false_auto_matches"] == 0:
                candidates.append((result["auto_matches"], margin, threshold, result))
    if not candidates:
        return {
            "threshold": 1.0,
            "minimum_margin": 1.0,
            "validation_auto_matches": 0,
            "validation_precision": 0.0,
            "selection_rule": "fail closed; no zero-false-auto-match validation point",
        }
    # Maximize validation coverage, then prefer a larger separation margin and
    # a larger probability threshold among equally covering candidates.
    auto_matches, margin, threshold, result = max(candidates, key=lambda item: (item[0], item[1], item[2]))
    return {
        "threshold": float(threshold),
        "minimum_margin": float(margin),
        "validation_auto_matches": int(auto_matches),
        "validation_settlements": int(result["settlements"]),
        "validation_precision": float(result["auto_match_precision"]),
        "selection_rule": "maximum validation coverage subject to zero false auto-matches; conservative tie-break on margin and threshold",
    }

def deterministic_exact(pair: EvaluationPair) -> bool:
    if pair.direction.value != "credit" or pair.bank_amount_paise != pair.settlement_amount_paise:
        return False
    if abs((pair.bank_date - pair.settlement_date).days) > 3:
        return False
    settlement = normalize_reference(pair.settlement_reference).replace(" ", "")
    bank = normalize_reference(pair.bank_reference).replace(" ", "")
    # The baseline represents a reasonable exact-evidence join, not an
    # intentionally weak straw man.
    significant = [token for token in normalize_reference(pair.settlement_reference).split() if len(token) >= 8]
    return any(token.replace(" ", "") in bank for token in significant) or settlement in bank


def evaluate_stress(
    groups: Sequence[dict[str, Any]],
    *,
    threshold: float,
    minimum_margin: float,
) -> dict[str, Any]:
    stress_groups = [group for group in groups if group["difficulty"] in {"damaged", "ambiguous"}]
    result = evaluate_policy(
        stress_groups,
        policy="hybrid",
        threshold=threshold,
        minimum_margin=minimum_margin,
    )
    result["scope"] = "damaged and ambiguous true-owner cases only"
    return result


def bootstrap_policy_delta(
    groups: Sequence[dict[str, Any]],
    *,
    threshold: float,
    minimum_margin: float,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(resamples):
        sample = [groups[rng.randrange(len(groups))] for _ in range(len(groups))]
        base = evaluate_policy(sample, policy="deterministic")
        hybrid = evaluate_policy(
            sample,
            policy="hybrid",
            threshold=threshold,
            minimum_margin=minimum_margin,
        )
        deltas.append(hybrid["straight_through_rate"] - base["straight_through_rate"])
    low, median, high = np.quantile(np.asarray(deltas), [0.025, 0.5, 0.975])
    return {
        "resamples": resamples,
        "unit": "settlement resampled within held-out test population",
        "straight_through_delta": {"p2_5": float(low), "median": float(median), "p97_5": float(high)},
    }


def expected_calibration_error(labels: np.ndarray, probabilities: np.ndarray, *, bins: int) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    result = 0.0
    for low, high in zip(edges[:-1], edges[1:], strict=True):
        include = (probabilities >= low) & (probabilities < high if high < 1.0 else probabilities <= high)
        if not np.any(include):
            continue
        confidence = float(probabilities[include].mean())
        accuracy = float(labels[include].mean())
        result += float(include.mean()) * abs(confidence - accuracy)
    return result


def write_predictions(
    path: Path,
    groups: Sequence[dict[str, Any]],
    *,
    threshold: float,
    minimum_margin: float,
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["merchant_id", "settlement_id", "bank_line_id", "label", "score", "difficulty", "policy_selected"])
        for group in groups:
            top = group["candidates"][0]
            second = group["candidates"][1]["score"]
            for item in group["candidates"]:
                pair = item["pair"]
                selected = (
                    item is top
                    and pair.direction.value == "credit"
                    and abs((pair.bank_date - pair.settlement_date).days) <= 3
                    and abs(pair.bank_amount_paise - pair.settlement_amount_paise) <= 1
                    and item["score"] >= threshold
                    and item["score"] - second >= minimum_margin
                )
                writer.writerow([pair.merchant_id, pair.settlement_id, pair.bank_line_id, pair.label, f"{item['score']:.10f}", pair.difficulty, int(selected)])


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    pair = result["pair_classifier_held_out"]
    baseline = result["policy_comparison"]["deterministic_baseline"]
    hybrid = result["policy_comparison"]["proofloom_hybrid"]
    stress = result["stress_test"]
    interval = result["merchant_bootstrap"]["straight_through_delta"]
    text = f"""# Proofloom evaluation results

## Executive result

On a merchant-group-held-out synthetic benchmark containing **{result['dataset']['test_settlements']} settlements / {result['dataset']['test_candidate_pairs']:,} candidate pairs**, the local ranker achieved **{pair['precision']:.1%} precision**, **{pair['recall']:.1%} recall**, and **{pair['pr_auc']:.3f} PR-AUC** at a threshold selected only on validation merchant groups.

At the policy level, the deterministic exact-evidence baseline auto-matched **{baseline['straight_through_rate']:.1%}** of settlements at **{baseline['auto_match_precision']:.1%} precision**. The hybrid policy auto-matched **{hybrid['straight_through_rate']:.1%}** at **{hybrid['auto_match_precision']:.1%} precision**, leaving **{hybrid['review_queue']}** cases for review and producing **{hybrid['false_auto_matches']}** false auto-matches in this synthetic test set. Its automation threshold (**{result['model']['policy_operating_point']['threshold']:.2f}**) and minimum score margin (**{result['model']['policy_operating_point']['minimum_margin']:.2f}**) were selected on validation merchants only, subject to zero validation false auto-matches.

## Held-out candidate-pair model

| Metric | Result |
|---|---:|
| Precision | {pair['precision']:.4f} |
| Recall | {pair['recall']:.4f} |
| F1 | {pair['f1']:.4f} |
| PR-AUC | {pair['pr_auc']:.4f} |
| ROC-AUC | {pair['roc_auc']:.4f} |
| Brier score | {pair['brier_score']:.4f} |
| 10-bin ECE | {pair['ece_10_bin']:.4f} |
| Threshold | {pair['threshold']:.4f} |

## Policy comparison

| Policy | Auto precision | Straight-through | Review queue | False auto-matches | Illustrative operating cost |
|---|---:|---:|---:|---:|---:|
| Deterministic exact-evidence baseline | {baseline['auto_match_precision']:.1%} | {baseline['straight_through_rate']:.1%} | {baseline['review_queue']} | {baseline['false_auto_matches']} | INR {baseline['illustrative_operating_cost_inr']:,} |
| Proofloom hybrid | {hybrid['auto_match_precision']:.1%} | {hybrid['straight_through_rate']:.1%} | {hybrid['review_queue']} | {hybrid['false_auto_matches']} | INR {hybrid['illustrative_operating_cost_inr']:,} |

The bootstrap median straight-through-rate delta is **{interval['median']:+.1%}** with a synthetic resampling interval of **[{interval['p2_5']:+.1%}, {interval['p97_5']:+.1%}]**. This interval describes the retained synthetic test population; it is not a confidence interval for live merchants.

## Stress slice

The damaged/ambiguous-only slice contains **{stress['settlements']}** settlements. The hybrid policy auto-matched **{stress['straight_through_rate']:.1%}** at **{stress['auto_match_precision']:.1%} precision**, with **{stress['false_auto_matches']}** false auto-matches and **{stress['review_queue']}** reviews.

## What is and is not claimed

- Merchant identifiers and narration vocabularies do not cross the train, validation and test groups.
- The deterministic baseline is a reasonable exact-evidence join, not an intentionally weak straw man.
- The model ranks candidates; exact money conservation, credit direction, booking windows, thresholds and human review remain deterministic controls.
- All records and labels are synthetic. The result is reproducible engineering evidence—not production merchant accuracy, recovered money, savings, ROI, or regulatory assurance.
- The illustrative cost model uses INR {result['economics']['false_auto_match_cost_inr']:,} per false auto-match and INR {result['economics']['manual_review_cost_inr']:,} per review.

## Reproduce

```bash
make setup
make evaluate
```

Raw predictions are retained in `predictions.csv`; the complete machine-readable result is in `results.json`.
"""
    path.write_text(text, encoding="utf-8")


def render_evaluation_figure(path: Path, result: dict[str, Any]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pair = result["pair_classifier_held_out"]
    baseline = result["policy_comparison"]["deterministic_baseline"]
    hybrid = result["policy_comparison"]["proofloom_hybrid"]
    labels = ["Pair precision", "Pair recall", "PR-AUC", "Straight-through", "Auto precision"]
    values = [pair["precision"], pair["recall"], pair["pr_auc"], hybrid["straight_through_rate"], hybrid["auto_match_precision"]]
    fig, ax = plt.subplots(figsize=(12, 5.2))
    positions = np.arange(len(labels))
    bars = ax.bar(positions, values)
    ax.set_ylim(0, 1.08)
    ax.set_xticks(positions, labels)
    ax.set_ylabel("Held-out synthetic result")
    ax.set_title("Proofloom — measured candidate ranking and bounded close policy")
    ax.grid(axis="y", alpha=0.22)
    for bar, value in zip(bars, values, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.025, f"{value:.1%}" if value <= 1 else str(value), ha="center", va="bottom")
    fig.text(
        0.01,
        0.01,
        f"Merchant-group holdout · {result['dataset']['test_settlements']} settlements · baseline STP {baseline['straight_through_rate']:.1%} · synthetic data only",
        fontsize=9,
    )
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
