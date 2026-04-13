import json
from pathlib import Path

from src.services.answer_service import ask_question
from src.config import ROOT_DIR

EVAL_FILE = ROOT_DIR / "eval" / "gold_questions_v6.json"
RESULTS_FILE = ROOT_DIR / "eval" / "eval_results_v6.json"


def evaluate_system(test_cases):
    results = []

    for case in test_cases:
        question = case["question"]
        expected_answered = case["expected_answered"]

        result = ask_question(question=question, top_k=4)

        actual_answered = bool(result.get("answered", False))

        results.append(
            {
                "question": question,
                "category": case.get("category", "unknown"),
                "expected_answered": expected_answered,
                "actual_answered": actual_answered,
                "answered_correctly": actual_answered == expected_answered,
                "answer": result.get("answer"),
                "confidence": result.get("confidence"),
                "grounding": result.get("grounding"),
                "top_source": result["sources"][0]["doc_name"] if result.get("sources") else None,
            }
        )

    return results


def summarize(results):
    total = len(results)
    correct = sum(1 for r in results if r["answered_correctly"])

    supported = [r for r in results if r["expected_answered"]]
    unsupported = [r for r in results if not r["expected_answered"]]

    supported_correct = sum(1 for r in supported if r["answered_correctly"])
    unsupported_correct = sum(1 for r in unsupported if r["answered_correctly"])

    return {
        "total": total,
        "accuracy": correct / total if total else 0.0,
        "supported_accuracy": supported_correct / len(supported) if supported else 0.0,
        "unsupported_accuracy": unsupported_correct / len(unsupported) if unsupported else 0.0,
    }


def main():
    with EVAL_FILE.open("r", encoding="utf-8") as f:
        test_cases = json.load(f)

    results = evaluate_system(test_cases)
    summary = summarize(results)

    payload = {
        "summary": summary,
        "results": results,
    }

    with RESULTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("V6 Summary:")
    print(json.dumps(summary, indent=2))
    print(f"Saved results to {RESULTS_FILE}")


if __name__ == "__main__":
    main()