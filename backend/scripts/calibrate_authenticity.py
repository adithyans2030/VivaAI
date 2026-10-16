"""Calibration script for VivaIQ Authenticity Analyzer.

Evaluates natural conversational speech vs. scripted / read-aloud responses
across the 6 advisory signals to establish empirical thresholds and false-positive rates.
"""

import json
from pathlib import Path
import sys

# Ensure backend directory is in sys.path
import os
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DEMO_MODE", "true")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.authenticity import AuthenticityAnalyzer, AuthenticityLikelihood


def run_calibration():
    analyzer = AuthenticityAnalyzer()

    # 1. Natural Spontaneous Speech Samples (Ground Truth: Natural)
    natural_samples = [
        {
            "id": "nat_1",
            "text": "Well, um, as I understand it, deadlocks happen when four conditions are met. First, mutual exclusion, like when a process holds a resource exclusively. Then hold and wait... uh, no preemption, and circular wait. If you break even one, deadlocks can't happen.",
            "timestamps": [
                {"word": "Well,", "start": 0.0, "end": 0.4},
                {"word": "um,", "start": 0.45, "end": 0.8},
                {"word": "as", "start": 1.2, "end": 1.35},
                {"word": "I", "start": 1.35, "end": 1.45},
                {"word": "understand", "start": 1.45, "end": 1.95},
                {"word": "it,", "start": 1.95, "end": 2.1},
                {"word": "deadlocks", "start": 2.3, "end": 2.8},
            ],
            "latency": 1.4,
            "duration": 9.2,
            "refs": ["Deadlock occurs when four conditions hold simultaneously: mutual exclusion, hold and wait, no preemption, circular wait."],
        },
        {
            "id": "nat_2",
            "text": "The TLB is basically an associative cache, right? Because virtual memory translation takes two trips to RAM, the hardware caches the recent page-to-frame translations. Actually, hit rates are usually above 95% in modern processors.",
            "timestamps": [
                {"word": "The", "start": 0.0, "end": 0.2},
                {"word": "TLB", "start": 0.2, "end": 0.6},
                {"word": "is", "start": 0.6, "end": 0.75},
                {"word": "basically", "start": 0.8, "end": 1.3},
                {"word": "an", "start": 1.35, "end": 1.45},
                {"word": "associative", "start": 1.45, "end": 2.1},
            ],
            "latency": 1.8,
            "duration": 8.0,
            "refs": ["A Translation Lookaside Buffer is a hardware cache that stores virtual-to-physical address mappings."],
        },
    ]

    # 2. Scripted / Note-Reading Samples (Ground Truth: Scripted)
    scripted_samples = [
        {
            "id": "scr_1",
            "text": "Deadlock occurs when four conditions hold simultaneously mutual exclusion hold and wait no preemption circular wait. A process may hold allocated resources while awaiting additional resources.",
            "timestamps": [
                # Metronomic, mid-clause pauses, zero disfluency
                {"word": "Deadlock", "start": 0.0, "end": 0.35},
                {"word": "occurs", "start": 0.36, "end": 0.70},
                {"word": "when", "start": 0.71, "end": 0.95},
                {"word": "four", "start": 1.50, "end": 1.80},  # Mid-clause pause at line break
                {"word": "conditions", "start": 1.81, "end": 2.25},
            ],
            "latency": 0.15,  # Superhuman rapid onset
            "duration": 6.5,
            "refs": ["Deadlock occurs when four conditions hold simultaneously: mutual exclusion, hold and wait, no preemption, circular wait. A process may hold allocated resources while awaiting additional resources."],
        },
        {
            "id": "scr_2",
            "text": "A critical section is a segment of code in which a process may be changing common variables updating a table or writing a file. Mutual exclusion ensures that when one process executes its critical section no other processes are allowed to execute.",
            "timestamps": [
                {"word": "A", "start": 0.0, "end": 0.15},
                {"word": "critical", "start": 0.16, "end": 0.50},
                {"word": "section", "start": 0.51, "end": 0.85},
            ],
            "latency": 0.10,
            "duration": 7.8,
            "refs": ["A critical section is a segment of code in which a process may be changing common variables, updating a table, or writing a file. Mutual exclusion ensures that when one process executes its critical section no other processes are allowed to execute."],
        },
    ]

    print("=" * 60)
    print("VIVAIQ AUTHENTICITY CALIBRATION BENCHMARK")
    print("=" * 60)

    # Evaluate Natural
    natural_results = []
    for sample in natural_samples:
        report = analyzer.analyze_turn(
            turn_number=2,
            student_text=sample["text"],
            reference_chunks=sample["refs"],
            word_timestamps=sample["timestamps"],
            onset_latency_seconds=sample["latency"],
            audio_duration_seconds=sample["duration"],
            question_type="conceptual",
        )
        natural_results.append((sample["id"], report))
        print(f"Sample {sample['id']} (Natural): Likelihood={report.likelihood.value}, Risk={report.composite_risk_score_0_1:.2f}, Conf={report.confidence:.2f}")

    # Evaluate Scripted
    scripted_results = []
    for sample in scripted_samples:
        report = analyzer.analyze_turn(
            turn_number=2,
            student_text=sample["text"],
            reference_chunks=sample["refs"],
            word_timestamps=sample["timestamps"],
            onset_latency_seconds=sample["latency"],
            audio_duration_seconds=sample["duration"],
            question_type="conceptual",
        )
        scripted_results.append((sample["id"], report))
        print(f"Sample {sample['id']} (Scripted): Likelihood={report.likelihood.value}, Risk={report.composite_risk_score_0_1:.2f}, Conf={report.confidence:.2f}")

    # Compute False Positive / False Negative Rates
    false_positives = sum(1 for _, r in natural_results if r.likelihood in (AuthenticityLikelihood.HIGH, AuthenticityLikelihood.MEDIUM))
    false_negatives = sum(1 for _, r in scripted_results if r.likelihood == AuthenticityLikelihood.LOW)

    fp_rate = (false_positives / len(natural_results)) * 100
    fn_rate = (false_negatives / len(scripted_results)) * 100

    print("-" * 60)
    print(f"Calibration Complete:")
    print(f"  Natural Samples: {len(natural_results)} | False Positives: {false_positives} ({fp_rate:.1f}%)")
    print(f"  Scripted Samples: {len(scripted_results)} | False Negatives: {false_negatives} ({fn_rate:.1f}%)")
    print("=" * 60)

    return {
        "false_positive_rate": fp_rate,
        "false_negative_rate": fn_rate,
        "total_evaluated": len(natural_results) + len(scripted_results),
    }


if __name__ == "__main__":
    run_calibration()
