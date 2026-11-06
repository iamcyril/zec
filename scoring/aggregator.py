"""Multi-signal score aggregation for Zecpath AI Platform.

Combines scores from up to four evaluation signals into a single weighted
final score and produces a hiring recommendation.

Decision thresholds
-------------------
* ``final_score >= select_at`` → ``"selected"``
* ``select_at > final_score >= hold_at`` → ``"hold"``
* ``final_score < hold_at`` → ``"rejected"``

Weights are renormalised over whichever signals are present, so passing a
subset of signals (e.g. no ``technical`` score yet) gives a fair result.

All aggregation results are emitted via :func:`~utils.logger.log_ai_event`
with ``event="scoring.aggregated"``.
"""

from __future__ import annotations

from utils.logger import get_logger, log_ai_event

logger = get_logger("zecpath.scoring")

# Default weight map — must sum to 1.0 across all four signals.
_DEFAULT_WEIGHTS: dict[str, float] = {
    "ats": 0.30,
    "screening": 0.20,
    "interview": 0.30,
    "technical": 0.20,
}

# Valid decision labels
_DECISION_SELECTED = "selected"
_DECISION_HOLD = "hold"
_DECISION_REJECTED = "rejected"


def aggregate(
    scores: dict[str, float],
    weights: dict[str, float] | None = None,
    select_at: float = 75.0,
    hold_at: float = 55.0,
    candidate_id: str = "unknown",
    job_id: str = "unknown",
) -> dict[str, float | str]:
    """Aggregate per-signal scores into a final hiring score and decision.

    Args:
        scores: Mapping of signal name → score (0-100).
            Valid keys: ``"ats"``, ``"screening"``, ``"interview"``, ``"technical"``.
        weights: Optional override weight map.  If ``None``, uses
            :data:`_DEFAULT_WEIGHTS`.  Weights are renormalised over
            whichever keys appear in both ``scores`` and ``weights``.
        select_at: Score threshold (inclusive) for ``"selected"`` decision.
        hold_at: Score threshold (inclusive) for ``"hold"`` decision.
            Candidates below ``hold_at`` are ``"rejected"``.
        candidate_id: Opaque candidate identifier for audit logs.
        job_id: Opaque job identifier for audit logs.

    Returns:
        Dict with keys:

        * ``"final_score"`` (float, 0-100, 2 dp)
        * ``"decision"`` (str: ``"selected"`` | ``"hold"`` | ``"rejected"``)

    Raises:
        ValueError: If ``scores`` has no keys in common with ``weights``.

    Example:
        >>> aggregate({"ats": 90, "screening": 80, "interview": 85})
        {'final_score': 87.5, 'decision': 'selected'}

    """
    weight_map = weights if weights is not None else _DEFAULT_WEIGHTS

    # Determine the overlap between supplied scores and weight map.
    common_keys = [k for k in scores if k in weight_map]
    if not common_keys:
        raise ValueError(
            f"No overlap between score keys {list(scores.keys())!r} "
            f"and weight map keys {list(weight_map.keys())!r}."
        )

    # Renormalise weights so they sum to 1.0 over the present keys.
    raw_total = sum(weight_map[k] for k in common_keys)
    normalised: dict[str, float] = {k: weight_map[k] / raw_total for k in common_keys}

    # Weighted sum.
    final_score = round(sum(scores[k] * normalised[k] for k in common_keys), 2)

    # Decision.
    if final_score >= select_at:
        decision = _DECISION_SELECTED
    elif final_score >= hold_at:
        decision = _DECISION_HOLD
    else:
        decision = _DECISION_REJECTED

    log_ai_event(
        "scoring.aggregated",
        candidate_id=candidate_id,
        job_id=job_id,
        scores_used={k: scores[k] for k in common_keys},
        weights_used=normalised,
        final_score=final_score,
        decision=decision,
        select_at=select_at,
        hold_at=hold_at,
    )
    logger.info(
        "Aggregated score for candidate %s / job %s: %.2f → %s",
        candidate_id,
        job_id,
        final_score,
        decision,
    )
    return {"final_score": final_score, "decision": decision}
