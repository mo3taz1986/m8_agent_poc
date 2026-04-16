from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

# ── Store location ─────────────────────────────────────────────────────────
# Default path — can be overridden via METADATA_STORE_PATH env variable
# or by passing store_path directly to load_metadata_store().
_DEFAULT_STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "metadata_store.json"

# ── Stopwords to exclude from keyword matching ─────────────────────────────
_STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "this", "that", "these", "those", "it", "its", "we", "our",
    "you", "your", "they", "them", "their", "all", "as", "if", "into",
    "about", "after", "before", "up", "out", "over", "just", "also",
    "more", "so", "not", "no", "new", "build", "create", "need", "needs",
    "want", "wants", "require", "requires",
}

# ── Type aliases ───────────────────────────────────────────────────────────
# Maps the Meaning Agent's resolved_category values to metadata store types.
# They are already aligned but this makes the contract explicit.
_CATEGORY_TO_TYPE: Dict[str, str] = {
    "interactive_dashboard": "interactive_dashboard",
    "reporting_output":      "reporting_output",
    "structured_extract":    "structured_extract",
    "data_view":             "data_view",
    "data_pipeline":         "data_pipeline",
    "integration_request":   "integration_request",
    "workflow_automation":   "workflow_automation",
    "analytical_model":      "analytical_model",
    "generic_business_request": "",  # no type filter — skip metadata check
}


def load_metadata_store(store_path: Optional[Path] = None) -> List[Dict]:
    """
    Load the metadata asset store from disk.
    Returns an empty list and logs a warning if the file is missing.
    """
    path = store_path or _DEFAULT_STORE_PATH

    if not path.exists():
        import warnings
        warnings.warn(
            f"Metadata store not found at {path}. "
            "Metadata Agent will return NEW for all requests. "
            "Place metadata_store.json at src/data/metadata_store.json to enable overlap detection.",
            stacklevel=2,
        )
        return []

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _tokenize(text: str) -> Set[str]:
    """Lowercase tokenisation with stopword removal."""
    tokens = re.findall(r"\b[a-z0-9]+\b", (text or "").lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) >= 3}


def _extract_signals_from_requirement(requirement_state: Dict) -> Set[str]:
    """
    Pull keyword signals from the current requirement state.
    Combines: original request, scope, stakeholders, data_sources,
    business_objective, and success_criteria.
    """
    fields = [
        requirement_state.get("original_request", ""),
        requirement_state.get("scope", ""),
        requirement_state.get("stakeholders", ""),
        requirement_state.get("data_sources", ""),
        requirement_state.get("business_objective", ""),
        requirement_state.get("success_criteria", ""),
    ]
    combined = " ".join(str(f) for f in fields if f)
    return _tokenize(combined)


def _score_asset(asset: Dict, signals: Set[str]) -> Dict:
    """
    Score a single asset against the extracted keyword signals.

    Scoring strategy:
    - Tags are the strongest signal (weight 3) — deliberately keyword-rich
    - Description carries semantic weight (weight 2)
    - Domain, stakeholders, data_sources contribute supporting evidence (weight 1 each)
    - Name provides a secondary title match (weight 2)

    Returns normalised score 0.0–1.0 and match detail.
    """
    if not signals:
        return {"score": 0.0, "matched_signals": [], "matched_fields": {}}

    tag_tokens        = _tokenize(" ".join(asset.get("tags", [])))
    desc_tokens       = _tokenize(asset.get("description", ""))
    domain_tokens     = _tokenize(" ".join(asset.get("domain", [])))
    stakeholder_tokens= _tokenize(" ".join(asset.get("stakeholders", [])))
    source_tokens     = _tokenize(" ".join(asset.get("data_sources", [])))
    name_tokens       = _tokenize(asset.get("name", ""))

    matched_by_field: Dict[str, List[str]] = {}
    weighted_hits = 0.0

    def _check(field_name: str, field_tokens: Set[str], weight: float) -> None:
        nonlocal weighted_hits
        hits = sorted(signals.intersection(field_tokens))
        if hits:
            matched_by_field[field_name] = hits
            weighted_hits += len(hits) * weight

    _check("tags",        tag_tokens,         3.0)
    _check("name",        name_tokens,        2.0)
    _check("description", desc_tokens,        2.0)
    _check("domain",      domain_tokens,      1.0)
    _check("stakeholders",stakeholder_tokens, 1.0)
    _check("data_sources",source_tokens,      1.0)

    all_matched = sorted({t for hits in matched_by_field.values() for t in hits})

    # Normalise: maximum possible score = all signals matching tags + name + desc
    max_possible = len(signals) * (3.0 + 2.0 + 2.0)
    score = min(weighted_hits / max_possible, 1.0) if max_possible > 0 else 0.0

    return {
        "score": round(score, 4),
        "matched_signals": all_matched,
        "matched_fields": matched_by_field,
    }


def retrieve_candidate_assets(
    requirement_state: Dict,
    resolved_category: str,
    top_k: int = 5,
    min_score: float = 0.05,
    store_path: Optional[Path] = None,
) -> List[Dict]:
    """
    Retrieve the top-k most relevant existing assets for a given requirement.

    Parameters
    ----------
    requirement_state : Dict
        The current requirement state — used to extract keyword signals.
    resolved_category : str
        The delivery category resolved by the Meaning Agent
        e.g. "interactive_dashboard", "data_pipeline".
    top_k : int
        Maximum number of candidates to return.
    min_score : float
        Minimum similarity score to include in results (filters noise).
    store_path : Optional[Path]
        Override the default metadata store path.

    Returns
    -------
    List of candidate dicts, each containing:
        asset_id, name, type, domain, description, stakeholders,
        data_sources, tags, owner, status,
        score, matched_signals, matched_fields
    """
    asset_type = _CATEGORY_TO_TYPE.get(resolved_category, "")

    # generic_business_request has no mapped type — skip lookup
    if not asset_type:
        return []

    store = load_metadata_store(store_path)
    if not store:
        return []

    # Hard filter: only consider assets of the same delivery type
    same_type_assets = [a for a in store if a.get("type") == asset_type]
    if not same_type_assets:
        return []

    signals = _extract_signals_from_requirement(requirement_state)
    if not signals:
        return []

    scored: List[Dict] = []
    for asset in same_type_assets:
        result = _score_asset(asset, signals)
        if result["score"] >= min_score:
            candidate = {
                "asset_id":        asset.get("asset_id"),
                "name":            asset.get("name"),
                "type":            asset.get("type"),
                "domain":          asset.get("domain", []),
                "description":     asset.get("description", ""),
                "stakeholders":    asset.get("stakeholders", []),
                "data_sources":    asset.get("data_sources", []),
                "tags":            asset.get("tags", []),
                "owner":           asset.get("owner", ""),
                "status":          asset.get("status", ""),
                "score":           result["score"],
                "matched_signals": result["matched_signals"],
                "matched_fields":  result["matched_fields"],
            }
            scored.append(candidate)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
