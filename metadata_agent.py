from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from src.retrievers.metadata_retriever import retrieve_candidate_assets

# ── Thresholds ─────────────────────────────────────────────────────────────
# These determine the REUSE / EXTEND / NEW decision boundary.
# Tuned for a 100-asset store — raise REUSE_THRESHOLD as the store grows
# and scores become more discriminating.
REUSE_THRESHOLD   = 0.65   # score >= this → REUSE
EXTEND_THRESHOLD  = 0.35   # score >= this → EXTEND
# score <  EXTEND_THRESHOLD → NEW

# Maximum candidates to retrieve and evaluate
TOP_K = 5


class MetadataAgent:
    """
    Validates a new requirement against the enterprise metadata store and
    recommends one of three actions:

      REUSE   — a sufficiently similar asset already exists
      EXTEND  — a related asset exists that could be extended
      NEW     — no meaningful overlap found — proceed as a new build

    Constraints (from the BRD):
    - Cannot define category — receives shape from the Meaning Agent
    - Validates only — does not influence routing decisions
    - Runs after shape lock, before the BA Agent begins
    - Returns a structured result the Leader stores on the session
    """

    def __init__(self, store_path: Optional[Path] = None) -> None:
        self._store_path = store_path

    def evaluate(
        self,
        requirement_state: Dict,
        resolved_category: str,
    ) -> Dict:
        """
        Evaluate a requirement against existing enterprise assets.

        Parameters
        ----------
        requirement_state : Dict
            Current requirement state from ba_service.
        resolved_category : str
            Delivery category locked by the Meaning Agent
            e.g. "interactive_dashboard", "data_pipeline".

        Returns
        -------
        Dict with keys:
            recommendation  — "REUSE" | "EXTEND" | "NEW"
            confidence      — float 0.0–1.0 (top candidate score)
            top_match       — the best matching asset dict, or None
            candidates      — list of all scored candidates
            rationale       — human-readable explanation string
            skipped         — True if lookup was skipped (generic category or no store)
        """
        # If shape is not specific enough, skip the lookup entirely.
        # A generic_business_request cannot be meaningfully matched.
        if not resolved_category or resolved_category == "generic_business_request":
            return self._skipped_result(
                reason="Shape not specific enough for metadata validation. "
                       "The Meaning Agent must resolve a specific delivery category "
                       "before metadata overlap can be assessed."
            )

        candidates = retrieve_candidate_assets(
            requirement_state=requirement_state,
            resolved_category=resolved_category,
            top_k=TOP_K,
            store_path=self._store_path,
        )

        # No store or no assets of this type — treat as new
        if not candidates:
            return self._new_result(
                confidence=0.0,
                candidates=[],
                reason=f"No existing {resolved_category.replace('_', ' ')} assets found "
                       f"in the metadata store. This appears to be a new capability."
            )

        top = candidates[0]
        top_score = top["score"]

        if top_score >= REUSE_THRESHOLD:
            return self._reuse_result(top, candidates)

        if top_score >= EXTEND_THRESHOLD:
            return self._extend_result(top, candidates)

        return self._new_result(
            confidence=top_score,
            candidates=candidates,
            reason=f"No existing asset closely matches this requirement. "
                   f"Best overlap was {top['name']!r} at {top_score:.0%} similarity — "
                   f"below the {EXTEND_THRESHOLD:.0%} threshold for an extension recommendation. "
                   f"Proceeding as a new build."
        )

    # ── Private result builders ────────────────────────────────────────────

    def _reuse_result(self, top: Dict, candidates: List[Dict]) -> Dict:
        matched = ", ".join(top.get("matched_signals", [])[:5]) or "multiple signals"
        return {
            "recommendation": "REUSE",
            "confidence":     top["score"],
            "top_match":      top,
            "candidates":     candidates,
            "skipped":        False,
            "rationale": (
                f"A closely matching asset already exists: {top['name']!r} "
                f"(owned by {top['owner']}, status: {top['status']}). "
                f"Similarity score: {top['score']:.0%}. "
                f"Matched on: {matched}. "
                f"Recommended action: review this asset before starting a new build — "
                f"it may already meet the requirement or require only minor changes."
            ),
        }

    def _extend_result(self, top: Dict, candidates: List[Dict]) -> Dict:
        matched = ", ".join(top.get("matched_signals", [])[:5]) or "several signals"
        return {
            "recommendation": "EXTEND",
            "confidence":     top["score"],
            "top_match":      top,
            "candidates":     candidates,
            "skipped":        False,
            "rationale": (
                f"A related asset exists that may be extendable: {top['name']!r} "
                f"(owned by {top['owner']}, status: {top['status']}). "
                f"Similarity score: {top['score']:.0%}. "
                f"Matched on: {matched}. "
                f"Recommended action: evaluate whether this requirement can be delivered "
                f"by extending the existing asset rather than building from scratch."
            ),
        }

    @staticmethod
    def _new_result(confidence: float, candidates: List[Dict], reason: str) -> Dict:
        return {
            "recommendation": "NEW",
            "confidence":     confidence,
            "top_match":      candidates[0] if candidates else None,
            "candidates":     candidates,
            "skipped":        False,
            "rationale":      reason,
        }

    @staticmethod
    def _skipped_result(reason: str) -> Dict:
        return {
            "recommendation": "NEW",
            "confidence":     0.0,
            "top_match":      None,
            "candidates":     [],
            "skipped":        True,
            "rationale":      reason,
        }

    # ── Static helpers for building user-facing messages ──────────────────

    @staticmethod
    def build_opening_note(metadata_result: Dict) -> Optional[str]:
        """
        Build a short user-facing note to prepend to the BA Agent's opening
        message when a REUSE or EXTEND recommendation is returned.

        Returns None for NEW — no note is shown, BA proceeds normally.
        """
        if metadata_result.get("skipped"):
            return None

        rec = metadata_result.get("recommendation")
        top = metadata_result.get("top_match")

        if rec == "REUSE" and top:
            return (
                f"Before we begin, I found an existing asset that may already cover this: "
                f"**{top['name']}** (owned by {top['owner']}). "
                f"You may want to review it before we proceed with a new build."
            )

        if rec == "EXTEND" and top:
            return (
                f"There is a related asset that may be extendable: "
                f"**{top['name']}** (owned by {top['owner']}). "
                f"We can proceed with the new requirement — but it is worth checking "
                f"whether an extension would be more efficient."
            )

        return None
