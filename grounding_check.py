import re
from typing import Dict, List


def tokenize(text: str) -> List[str]:
    """
    Lowercase tokenization for grounding checks.
    """
    return re.findall(r"\b\w+\b", text.lower())


def normalize_answer_text(answer: str) -> str:
    """
    Remove markdown-style evidence blocks and normalize whitespace.
    """
    if not answer:
        return ""

    text = answer.strip()

    # Remove common markdown evidence headings and everything after them
    split_patterns = [
        r"\n\*\*Evidence:\*\*",
        r"\nEvidence:",
        r"\nSupporting evidence:",
    ]

    for pattern in split_patterns:
        parts = re.split(pattern, text, maxsplit=1, flags=re.IGNORECASE)
        text = parts[0].strip()

    return text


def compute_grounding_score(answer: str, retrieved_chunks: List[Dict]) -> float:
    """
    Estimate whether the answer is grounded in the retrieved evidence
    using token overlap against the combined retrieved chunk text.
    """
    clean_answer = normalize_answer_text(answer)
    answer_tokens = set(tokenize(clean_answer))

    if not answer_tokens:
        return 0.0

    combined_context = " ".join(chunk.get("text", "") for chunk in retrieved_chunks)
    context_tokens = set(tokenize(combined_context))

    if not context_tokens:
        return 0.0

    overlap = answer_tokens.intersection(context_tokens)
    return len(overlap) / len(answer_tokens)


def verify_grounding(
    answer: str,
    retrieved_chunks: List[Dict],
    min_grounding_score: float = 0.20,
) -> Dict:
    """
    Return a grounding verdict and score.
    """
    grounding_score = compute_grounding_score(answer, retrieved_chunks)

    if answer.strip() == "I do not have enough evidence from the retrieved context.":
        verdict = "refused"
        grounded = True
    elif grounding_score >= min_grounding_score:
        verdict = "grounded"
        grounded = True
    else:
        verdict = "unsupported"
        grounded = False

    return {
        "grounding_score": float(grounding_score),
        "grounding_verdict": verdict,
        "grounded": grounded,
    }