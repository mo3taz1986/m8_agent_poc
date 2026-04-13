import json
from pathlib import Path
from typing import Dict, List

from src.agent_v4 import process_question as process_v4
from src.agent_v5 import process_question as process_v5
from src.config import ROOT_DIR

EVAL_FILE = ROOT_DIR / "eval" / "gold_questions.json"
COMPARE_RESULTS_FILE = ROOT_DIR / "eval" / "eval_comparison.json"


def evaluate_system(process_fn, test_cases: List[Dict]) -> List[Dict]:
    results = []

    for case in test_cases:
        question = case["question"]
        expected_answered = case["expected_answered"]

        result = process_fn(question)

        actual_answered = bool(result.get("answered", False))

        results.append({
            "question": question,
            "expected_answered": expected_answered,
            "actual_answered": actual_answered,
            "answered_correctly": actual_answered == expected_answered,
            "answer": result.get("answer"),
            "top_doc": (
                result["retrieved_chunks"][0]["doc_name"]
                if result.get("retrieved_chunks")
                else None
            ),
        })

    return results


def summarize(results: List[Dict]) -> Dict:
    total = len(results)
    correct = sum(1 for r in results if r["answered_correctly"])

    supported = [r for r in results if r["expected_answered"]]
    unsupported = [r for r in results if not r["expected_answered"]]

    supported_correct = sum(1 for r in supported if r["answered_correctly"])
    unsupported_correct = sum(1 for r in unsupported if r["answered_correctly"])

    return {
        "total": total,
        "accuracy": correct / total if total else 0.0,
        "supported_accuracy": (
            supported_correct / len(supported) if supported else 0.0
        ),
        "unsupported_accuracy": (
            unsupported_correct / len(unsupported) if unsupported else 0.0
        ),
    }


def compare(v4_results: List[Dict], v5_results: List[Dict]) -> List[Dict]:
    comparisons = []

    for v4, v5 in zip(v4_results, v5_results):
        comparisons.append({
            "question": v4["question"],
            "expected_answered": v4["expected_answered"],
            "v4_answered": v4["actual_answered"],
            "v5_answered": v5["actual_answered"],
            "v4_correct": v4["answered_correctly"],
            "v5_correct": v5["answered_correctly"],
            "improved": (not v4["answered_correctly"] and v5["answered_correctly"]),
            "regressed": (v4["answered_correctly"] and not v5["answered_correctly"]),
        })

    return comparisons


def main():
    with EVAL_FILE.open("r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print("Running V4 evaluation...")
    v4_results = evaluate_system(process_v4, test_cases)

    print("Running V5 evaluation...")
    v5_results = evaluate_system(process_v5, test_cases)

    v4_summary = summarize(v4_results)
    v5_summary = summarize(v5_results)
    comparison = compare(v4_results, v5_results)

    payload = {
        "v4_summary": v4_summary,
        "v5_summary": v5_summary,
        "comparison": comparison,
    }

    with COMPARE_RESULTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("\nV4 Summary:")
    print(json.dumps(v4_summary, indent=2))

    print("\nV5 Summary:")
    print(json.dumps(v5_summary, indent=2))

    print(f"\nSaved comparison to {COMPARE_RESULTS_FILE}")


if __name__ == "__main__":
    main()