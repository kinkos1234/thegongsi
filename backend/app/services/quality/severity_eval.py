"""Severity classification quality evaluation.

This is the first measurable accuracy harness for The Gongsi. It evaluates the
deterministic rule layer against a curated gold set and reports precision,
recall, F1, false positives, and false negatives by severity class.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from app.services.anomaly.detector import RULE_SET_VERSION, rule_based_match

LABELS = ("high", "med", "low")
DEFAULT_GOLD_PATH = Path(__file__).resolve().parents[3] / "data" / "severity_gold.json"
MIN_ACCURACY = 0.85
MIN_HIGH_RECALL = 0.9
MIN_MACRO_F1 = 0.8


def _normalize_label(label: str | None) -> str:
    if label in LABELS:
        return label
    return "low"


def load_gold_cases(path: Path | None = None) -> list[dict]:
    gold_path = path or DEFAULT_GOLD_PATH
    with gold_path.open("r", encoding="utf-8") as f:
        cases = json.load(f)
    if not isinstance(cases, list):
        raise ValueError("severity gold set must be a list")
    required = {"id", "report_nm", "expected"}
    for case in cases:
        missing = required - set(case)
        if missing:
            raise ValueError(f"severity gold case missing fields: {sorted(missing)}")
        if case["expected"] not in LABELS:
            raise ValueError(f"invalid expected label for {case['id']}: {case['expected']}")
    return cases


def _empty_label_metrics() -> dict[str, dict]:
    return {
        label: {
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
        }
        for label in LABELS
    }


def evaluate_cases(cases: Iterable[dict]) -> dict:
    rows = []
    confusion = {expected: {predicted: 0 for predicted in LABELS} for expected in LABELS}
    label_metrics = _empty_label_metrics()

    for case in cases:
        raw_prediction, reason, evidence = rule_based_match(case["report_nm"])
        predicted = _normalize_label(raw_prediction)
        expected = case["expected"]
        passed = predicted == expected
        confusion[expected][predicted] += 1
        rows.append({
            "id": case["id"],
            "report_nm": case["report_nm"],
            "expected": expected,
            "predicted": predicted,
            "passed": passed,
            "reason": reason or "규칙 매칭 없음",
            "evidence": evidence,
            "rationale": case.get("rationale"),
        })

    total = len(rows)
    passed_count = sum(1 for row in rows if row["passed"])
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in LABELS if other != label)
        fn = sum(confusion[label][other] for other in LABELS if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        label_metrics[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    false_positives = [
        row for row in rows
        if row["predicted"] in ("high", "med") and row["expected"] == "low"
    ]
    false_negatives = [
        row for row in rows
        if row["expected"] in ("high", "med") and row["predicted"] == "low"
    ]
    errors = [row for row in rows if not row["passed"]]
    accuracy = passed_count / total if total else 0.0
    macro_f1 = sum(label_metrics[label]["f1"] for label in LABELS) / len(LABELS)
    high_recall = label_metrics["high"]["recall"]
    meets_bar = (
        accuracy >= MIN_ACCURACY
        and macro_f1 >= MIN_MACRO_F1
        and high_recall >= MIN_HIGH_RECALL
    )

    return {
        "suite": "severity_gold_v1",
        "rule_set": RULE_SET_VERSION,
        "status": "pass" if meets_bar else "fail",
        "thresholds": {
            "min_accuracy": MIN_ACCURACY,
            "min_macro_f1": MIN_MACRO_F1,
            "min_high_recall": MIN_HIGH_RECALL,
        },
        "total": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "labels": label_metrics,
        "confusion": confusion,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "errors": errors,
    }


def evaluate_default_gold() -> dict:
    return evaluate_cases(load_gold_cases())
