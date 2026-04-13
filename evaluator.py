import json
import re
from pathlib import Path
from typing import Dict, List, Any

from src.agent_v5 import process_question
from src.config import ROOT_DIR


EVAL_FILE = ROOT_DIR / "eval" / "gold_questions.json"
EVAL_RESULTS_FILE = ROOT_DIR / "eval" / "eval_results.json"


def normalize_text(text: str) -> str:
    """
    Lowercase and collapse whitespace for consistent keyword checks.
    """
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def contains_expected_keywords(answer: str, expected_keywords: List[str]) -> Dict[str, Any]:
    """
    Check how many expected keywords or phrases appear in the answer.
    """
    normalized_answer = normalize_text(answer)
    matched = []

    for keyword in expected_keywords:
        if normalize_text(keyword) in normalized_answer:
            matched.append(keyword)

    total = len(expected_keywords)
    matched_count = len(matched)
    coverage = matched_count / total if total > 0 else None

    return {
        "matched_keywords": matched,
        "matched_count": matched_count,
        "total_expected_keywords": total,
        "keyword_coverage": coverage,
    }


def top_doc_match(retrieved_chunks: List[Dict], expected_doc: str | None) -> bool | None:
    """
    Check whether the top retrieved chunk matches the expected source doc.
    """
    if expected_doc is None:
        return None

    if not retrieved_chunks:
        return False

    return retrieved_chunks[0].get("doc_name") == expected_doc


def evaluate_one_case(test_case: Dict) -> Dict:
    """
    Run one evaluation case through the V5 agent and score the result.
    """
    question = test_case["question"]
    expected_answered = test_case["expected_answered"]
    expected_doc = test_case.get("expected_doc")
    expected_keywords = test_case.get("expected_keywords", [])

    result = process_question(question)

    actual_answered = bool(result.get("answered", False))
    answer = result.get("answer", "")
    retrieved_chunks = result.get("retrieved_chunks", [])
    grounding = result.get("grounding", {})

    answered_correctly = actual_answered == expected_answered
    doc_match = top_doc_match(retrieved_chunks, expected_doc)
    keyword_check = contains_expected_keywords(answer, expected_keywords)

    if expected_answered:
        answer_quality_pass = (
            actual_answered
            and (
                keyword_check["keyword_coverage"] is not None
                and keyword_check["keyword_coverage"] >= 0.34
            )
        )
    else:
        answer_quality_pass = not actual_answered

    return {
        "question": question,
        "notes": test_case.get("notes"),
        "expected_answered": expected_answered,
        "actual_answered": actual_answered,
        "answered_correctly": answered_correctly,
        "expected_doc": expected_doc,
        "top_retrieved_doc": retrieved_chunks[0].get("doc_name") if retrieved_chunks else None,
        "doc_match": doc_match,
        "answer": answer,
        "keyword_check": keyword_check,
        "answer_quality_pass": answer_quality_pass,
        "grounding": grounding,
        "top_chunks": retrieved_chunks,
    }


def summarize_results(results: List[Dict]) -> Dict:
    """
    Build a summary scorecard across all evaluation cases.
    """
    total = len(results)
    answered_correctly_count = sum(1 for r in results if r["answered_correctly"])
    quality_pass_count = sum(1 for r in results if r["answer_quality_pass"])

    supported_cases = [r for r in results if r["expected_answered"]]
    unsupported_cases = [r for r in results if not r["expected_answered"]]

    supported_answered_correctly = sum(1 for r in supported_cases if r["answered_correctly"])
    unsupported_answered_correctly = sum(1 for r in unsupported_cases if r["answered_correctly"])

    doc_match_cases = [r for r in supported_cases if r["doc_match"] is not None]
    doc_match_count = sum(1 for r in doc_match_cases if r["doc_match"] is True)

    return {
        "total_cases": total,
        "answered_correctly_count": answered_correctly_count,
        "answered_correctly_rate": answered_correctly_count / total if total else 0.0,
        "answer_quality_pass_count": quality_pass_count,
        "answer_quality_pass_rate": quality_pass_count / total if total else 0.0,
        "supported_case_count": len(supported_cases),
        "supported_answered_correctly_count": supported_answered_correctly,
        "supported_answered_correctly_rate": (
            supported_answered_correctly / len(supported_cases)
            if supported_cases else 0.0
        ),
        "unsupported_case_count": len(unsupported_cases),
        "unsupported_answered_correctly_count": unsupported_answered_correctly,
        "unsupported_answered_correctly_rate": (
            unsupported_answered_correctly / len(unsupported_cases)
            if unsupported_cases else 0.0
        ),
        "top_doc_match_count": doc_match_count,
        "top_doc_match_rate": (
            doc_match_count / len(doc_match_cases)
            if doc_match_cases else 0.0
        ),
    }


def main():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Evaluation file not found: {EVAL_FILE}")

    with EVAL_FILE.open("r", encoding="utf-8") as f:
        test_cases = json.load(f)

    results = []
    for idx, test_case in enumerate(test_cases, start=1):
        print(f"Running case {idx}/{len(test_cases)}: {test_case['question']}")
        result = evaluate_one_case(test_case)
        results.append(result)

    summary = summarize_results(results)

    payload = {
        "summary": summary,
        "results": results,
    }

    with EVAL_RESULTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("\nEvaluation complete.\n")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved detailed results to: {EVAL_RESULTS_FILE}")


if __name__ == "__main__":
    main()
