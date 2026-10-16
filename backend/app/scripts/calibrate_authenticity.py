"""Calibration utility for Authenticity Assessment Engine.

Computes precision, recall, and optimal thresholds across labeled benchmark
transcripts (spontaneous vs. reading_notes) to ensure balanced calibration.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from app.services.authenticity import AuthenticityAnalyzer, AuthenticityLikelihood


# Benchmark samples: ground truth labeled data
DEFAULT_BENCHMARK_DATA = [
    {
        "id": "sample-spontaneous-1",
        "ground_truth": "spontaneous",
        "transcript": (
            "Well, um, so the deadlock happens when four conditions are met. "
            "First is mutual exclusion, meaning only one thread can hold a resource at once. "
            "And, uh, then hold and wait, like where you hold something while asking for another. "
            "There is no preemption, and, um, finally circular wait."
        ),
        "reference_chunks": [
            "Deadlock occurs when four Coffman conditions hold: Mutual Exclusion, Hold and Wait, No Preemption, Circular Wait."
        ],
        "word_timestamps": [
            {"word": "Well,", "start": 1.2, "end": 1.5},
            {"word": "um,", "start": 1.6, "end": 1.9},
            {"word": "so", "start": 2.0, "end": 2.2},
            {"word": "the", "start": 2.2, "end": 2.4},
            {"word": "deadlock", "start": 2.4, "end": 2.9},
            {"word": "happens", "start": 2.9, "end": 3.4},
        ],
        "onset_latency_seconds": 1.8,
        "question_type": "conceptual",
    },
    {
        "id": "sample-reading-1",
        "ground_truth": "reading_notes",
        "transcript": (
            "Deadlock occurs when four Coffman conditions hold simultaneously: "
            "Mutual Exclusion wherein at least one resource is held in a non-shareable mode; "
            "Hold and Wait where a process must be holding at least one resource and requesting additional resources; "
            "No Preemption; and Circular Wait."
        ),
        "reference_chunks": [
            "Deadlock occurs when four Coffman conditions hold simultaneously: Mutual Exclusion wherein at least one resource is held in a non-shareable mode; Hold and Wait where a process must be holding at least one resource and requesting additional resources; No Preemption; and Circular Wait."
        ],
        "word_timestamps": [
            {"word": "Deadlock", "start": 0.2, "end": 0.6},
            {"word": "occurs", "start": 0.6, "end": 0.9},
            {"word": "when", "start": 0.9, "end": 1.1},
            {"word": "four", "start": 1.1, "end": 1.3},
            {"word": "Coffman", "start": 1.3, "end": 1.7},
            {"word": "conditions", "start": 1.7, "end": 2.2},
        ],
        "onset_latency_seconds": 0.3,
        "question_type": "conceptual",
    },
]


def run_calibration(benchmark_path: Path = None) -> Dict[str, Any]:
    """Run calibration analysis and output metrics."""
    analyzer = AuthenticityAnalyzer()

    data = DEFAULT_BENCHMARK_DATA
    if benchmark_path and benchmark_path.exists():
        with open(benchmark_path, "r", encoding="utf-8") as f:
            data = json.load(f)

    tp = fp = tn = fn = 0
    results = []

    for item in data:
        report = analyzer.analyze_turn(
            turn_number=1,
            student_text=item["transcript"],
            reference_chunks=item.get("reference_chunks", []),
            word_timestamps=item.get("word_timestamps"),
            onset_latency_seconds=item.get("onset_latency_seconds"),
            question_type=item.get("question_type", "conceptual"),
        )

        is_flagged = report.likelihood in (AuthenticityLikelihood.HIGH, AuthenticityLikelihood.MEDIUM)
        is_reading = item["ground_truth"] == "reading_notes"

        if is_flagged and is_reading:
            tp += 1
        elif is_flagged and not is_reading:
            fp += 1
        elif not is_flagged and not is_reading:
            tn += 1
        else:
            fn += 1

        results.append({
            "id": item["id"],
            "ground_truth": item["ground_truth"],
            "predicted_likelihood": report.likelihood.value,
            "risk_score": report.composite_risk_score_0_1,
            "reasons": report.reasons,
        })

    total = len(data)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    accuracy = (tp + tn) / max(1, total)

    summary = {
        "samples_evaluated": total,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "accuracy": round(accuracy, 3),
        "details": results,
    }

    print("\n" + "=" * 50)
    print("VivaIQ Authenticity Calibration Results")
    print("=" * 50)
    print(f"Total Samples: {total}")
    print(f"Accuracy:     {accuracy * 100:.1f}%")
    print(f"Precision:    {precision * 100:.1f}%")
    print(f"Recall:       {recall * 100:.1f}%")
    print("=" * 50 + "\n")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calibrate Authenticity Engine")
    parser.add_argument("--dataset", type=Path, default=None, help="Path to benchmark JSON")
    args = parser.parse_args()
    run_calibration(args.dataset)
