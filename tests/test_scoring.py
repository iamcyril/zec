"""Tests for scoring/aggregator.py."""

from __future__ import annotations

import pytest

from scoring.aggregator import aggregate


class TestAggregateDecisions:
    def test_selected_when_score_at_select_threshold(self) -> None:
        result = aggregate({"ats": 75.0, "screening": 75.0, "interview": 75.0, "technical": 75.0})
        assert result["decision"] == "selected"
        assert result["final_score"] == pytest.approx(75.0)

    def test_selected_when_score_above_select_threshold(self) -> None:
        result = aggregate({"ats": 90, "screening": 85, "interview": 88, "technical": 80})
        assert result["decision"] == "selected"

    def test_hold_when_score_between_thresholds(self) -> None:
        # 60 * 0.3 + 60 * 0.2 + 60 * 0.3 + 60 * 0.2 = 60
        result = aggregate({"ats": 60, "screening": 60, "interview": 60, "technical": 60})
        assert result["decision"] == "hold"
        assert result["final_score"] == pytest.approx(60.0)

    def test_rejected_when_score_below_hold_threshold(self) -> None:
        result = aggregate({"ats": 40, "screening": 40, "interview": 40, "technical": 40})
        assert result["decision"] == "rejected"

    def test_hold_at_boundary(self) -> None:
        """Score exactly at hold_at=55 should be 'hold' not 'rejected'."""
        result = aggregate({"ats": 55, "screening": 55, "interview": 55, "technical": 55})
        assert result["decision"] == "hold"

    def test_rejected_just_below_hold(self) -> None:
        result = aggregate({"ats": 54, "screening": 54, "interview": 54, "technical": 54})
        assert result["decision"] == "rejected"


class TestAggregateWeights:
    def test_partial_scores_renormalised(self) -> None:
        """With only ats and screening, weights renormalise to 0.6 and 0.4."""
        # ats=100, screening=0 → (100*0.3 + 0*0.2)/(0.3+0.2) = 30/0.5 = 60
        result = aggregate({"ats": 100, "screening": 0})
        assert result["final_score"] == pytest.approx(60.0)

    def test_custom_weights_applied(self) -> None:
        result = aggregate(
            {"ats": 80, "interview": 60},
            weights={"ats": 0.5, "interview": 0.5},
        )
        assert result["final_score"] == pytest.approx(70.0)

    def test_value_error_on_no_overlap(self) -> None:
        """Supplying scores with no matching weight keys must raise ValueError."""
        with pytest.raises(ValueError, match="No overlap"):
            aggregate({"unknown_signal": 80})

    def test_final_score_is_float(self) -> None:
        result = aggregate({"ats": 80, "screening": 70, "interview": 75, "technical": 65})
        assert isinstance(result["final_score"], float)

    def test_final_score_rounded_to_2dp(self) -> None:
        result = aggregate({"ats": 77, "screening": 63, "interview": 81, "technical": 59})
        assert result["final_score"] == round(result["final_score"], 2)  # type: ignore[arg-type]

    def test_custom_select_threshold(self) -> None:
        result = aggregate(
            {"ats": 80, "screening": 80, "interview": 80, "technical": 80},
            select_at=85,
        )
        assert result["decision"] == "hold"

    def test_custom_hold_threshold(self) -> None:
        result = aggregate(
            {"ats": 50, "screening": 50, "interview": 50, "technical": 50},
            hold_at=60,
        )
        assert result["decision"] == "rejected"
