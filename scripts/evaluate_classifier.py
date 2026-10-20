#!/usr/bin/env python3
"""Classifier evaluation script for Cerevyn Solutions PS04.

Evaluates the deterministic baseline classification engine against the fixed,
independent evaluation test set (sample_data/evaluation_tickets.json).

Calculates:
  - Exact Category Accuracy = (Correct Categories / Total) * 100
  - Priority Accuracy = (Correct Priorities / Total) * 100
  - Confusion Matrix across categories
  - Detailed per-ticket predictions and human-review flags
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.models.schemas import Category
from app.services.classifier import classify_ticket


def load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    """Load JSON evaluation fixtures."""
    if not dataset_path.exists():
        print(f"Error: Dataset file not found at {dataset_path}", file=sys.stderr)
        sys.exit(1)
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate(dataset_path: Path) -> Dict[str, Any]:
    """Execute evaluation and print formatted performance report."""
    tickets = load_dataset(dataset_path)
    total = len(tickets)
    if total == 0:
        print("Error: Evaluation dataset is empty.", file=sys.stderr)
        sys.exit(1)

    correct_categories = 0
    correct_priorities = 0
    correct_teams = 0
    flagged_for_review_count = 0

    all_categories = [c.value for c in Category]
    # confusion_matrix[expected][predicted]
    confusion_matrix: Dict[str, Dict[str, int]] = {
        exp: {pred: 0 for pred in all_categories} for exp in all_categories
    }

    results: List[Dict[str, Any]] = []

    for item in tickets:
        ticket_id = item["ticket_id"]
        msg = item["message"]
        exp_cat = item["expected_category"]
        exp_prio = item["expected_priority"]
        exp_team = item.get("expected_team")

        result = classify_ticket(msg)
        pred_cat = result.category.value
        pred_prio = result.priority.value
        pred_team = result.assigned_team.value

        cat_match = (pred_cat == exp_cat)
        prio_match = (pred_prio == exp_prio)
        team_match = (exp_team is None or pred_team == exp_team)

        if cat_match:
            correct_categories += 1
        if prio_match:
            correct_priorities += 1
        if team_match:
            correct_teams += 1
        if result.needs_human_review:
            flagged_for_review_count += 1

        if exp_cat in confusion_matrix and pred_cat in confusion_matrix[exp_cat]:
            confusion_matrix[exp_cat][pred_cat] += 1

        results.append({
            "ticket_id": ticket_id,
            "message": msg[:60] + "..." if len(msg) > 60 else msg,
            "exp_cat": exp_cat,
            "pred_cat": pred_cat,
            "cat_match": cat_match,
            "exp_prio": exp_prio,
            "pred_prio": pred_prio,
            "prio_match": prio_match,
            "confidence": result.confidence_score,
            "needs_review": result.needs_human_review,
        })

    cat_accuracy = (correct_categories / total) * 100.0
    prio_accuracy = (correct_priorities / total) * 100.0

    print("=" * 78)
    print(" CEREVYN SOLUTIONS PS04 - CLASSIFIER EVALUATION REPORT")
    print("=" * 78)
    print(f"Dataset File      : {dataset_path.relative_to(PROJECT_ROOT)}")
    print(f"Total Test Cases  : {total}")
    print(f"Correct Categories: {correct_categories}/{total}")
    print(f"Category Accuracy : {cat_accuracy:.2f}%")
    print(f"Priority Accuracy : {prio_accuracy:.2f}%")
    print(f"Flagged for Review: {flagged_for_review_count}/{total} (routed to human triage)")
    print("-" * 78)
    print("PER-TICKET EVALUATION BREAKDOWN:")
    print(f"{'ID':<10} {'Exp Cat':<10} {'Pred Cat':<10} {'Match':<6} {'Exp Prio':<9} {'Pred Prio':<9} {'Conf':<6} {'Review':<6}")
    print("-" * 78)
    for r in results:
        match_str = "PASS" if r["cat_match"] else "FAIL"
        rev_str = "YES" if r["needs_review"] else "NO"
        print(
            f"{r['ticket_id']:<10} {r['exp_cat']:<10} {r['pred_cat']:<10} {match_str:<6} "
            f"{r['exp_prio']:<9} {r['pred_prio']:<9} {r['confidence']:<6.2f} {rev_str:<6}"
        )

    print("-" * 78)
    print("CONFUSION MATRIX (Rows = Ground Truth Expected, Columns = Predicted):")
    col_title = "Expected \\ Pred"
    header = f"{col_title:<16}" + "".join(f"{c:>12}" for c in all_categories)
    print(header)
    print("-" * len(header))
    for exp in all_categories:
        row_str = f"{exp:<16}" + "".join(f"{confusion_matrix[exp][pred]:>12}" for pred in all_categories)
        print(row_str)
    print("=" * 78)

    return {
        "total": total,
        "correct_categories": correct_categories,
        "category_accuracy": round(cat_accuracy, 2),
        "priority_accuracy": round(prio_accuracy, 2),
        "flagged_for_review": flagged_for_review_count,
        "results": results,
    }


if __name__ == "__main__":
    dataset_file = PROJECT_ROOT / "sample_data" / "evaluation_tickets.json"
    if len(sys.argv) > 1:
        dataset_file = Path(sys.argv[1]).resolve()
    evaluate(dataset_file)
