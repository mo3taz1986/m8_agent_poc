import re
from typing import Dict, List, Set
 
 
# Common English stopwords that carry no semantic signal.
# Including these in token overlap artificially inflates grounding scores
# for low-information answers and deflates scores for correctly paraphrased
# answers (e.g. an LLM that answers "records must be kept for 7 years after
# account closure" using different connecting words than the source chunk).
STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "it", "its", "this",
    "that", "these", "those", "i", "we", "you", "he", "she", "they", "them",
    "their", "our", "your", "my", "his", "her", "all", "any", "each", "not",
    "no", "nor", "so", "yet", "both", "either", "neither", "as", "if",
    "then", "than", "when", "where", "which", "who", "what", "how", "also",
    "into", "about", "after", "before", "during", "through", "between",
    "above", "below", "up", "down", "out", "off", "over", "under", "again",
    "further", "once", "here", "there", "more", "most", "other", "such",
    "same", "own", "just", "too", "very", "s", "t", "only", "well",
}
 
 
def tokenize(text: str) -> List[str]:
    """
    Lowercase tokenization for grounding checks.
    """
    return re.findall(r"\b\w+\b", text.lower())
 
 
def tokenize_meaningful(text: str) -> Set[str]:
    """
    Tokenize and remove stopwords, returning only semantically meaningful
    tokens. This prevents common function words from inflating or deflating
    grounding scores when an LLM correctly paraphrases source content using
    different connecting vocabulary.
    """
    return {tok for tok in tokenize(text) if tok not in STOPWORDS}
 
 
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
    using meaningful token overlap against the combined retrieved chunk text.
 
    Stopwords are excluded from both the answer and context token sets before
    computing overlap. This fixes a regression where correctly paraphrased
    answers scored low because their connecting vocabulary differed from the
    source chunk, while trivially short answers scored high due to shared
    function words like "the", "is", and "a".
 
    Score = |answer_meaningful ∩ context_meaningful| / |answer_meaningful|
    """
    clean_answer = normalize_answer_text(answer)
    answer_tokens = tokenize_meaningful(clean_answer)
 
    if not answer_tokens:
        return 0.0
 
    combined_context = " ".join(chunk.get("text", "") for chunk in retrieved_chunks)
    context_tokens = tokenize_meaningful(combined_context)
 
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
