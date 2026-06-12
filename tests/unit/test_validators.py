"""Unit tests for validators.py"""
import pytest
from validators import (
    validate_weights,
    get_remaining_budget,
    validate_thresholds,
    validate_tier_boundaries,
)
from config import CRITERIA_NAMES, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, DEFAULT_TIER_BOUNDARIES


class TestValidateWeights:
    """Tests for validate_weights function."""

    def test_valid_default_vendor_weights(self):
        valid, msg = validate_weights(DEFAULT_WEIGHTS['Vendor'])
        assert valid is True
        assert msg == ""

    def test_valid_default_seller_weights(self):
        valid, msg = validate_weights(DEFAULT_WEIGHTS['Seller'])
        assert valid is True
        assert msg == ""

    def test_sum_exceeds_100(self):
        weights = {name: 11 for name in CRITERIA_NAMES}  # sum = 110
        valid, msg = validate_weights(weights)
        assert valid is False
        assert "exceeds 100 by 10" in msg

    def test_sum_below_100(self):
        weights = {name: 9 for name in CRITERIA_NAMES}  # sum = 90
        valid, msg = validate_weights(weights)
        assert valid is False
        assert "short of 100 by 10" in msg

    def test_negative_weight_rejected(self):
        weights = dict(zip(CRITERIA_NAMES, [100, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
        weights['overage'] = -1
        valid, msg = validate_weights(weights)
        assert valid is False
        assert "must be between 0 and 100" in msg

    def test_weight_above_100_rejected(self):
        weights = {name: 0 for name in CRITERIA_NAMES}
        weights['overage'] = 101
        valid, msg = validate_weights(weights)
        assert valid is False
        assert "must be between 0 and 100" in msg

    def test_all_zero_weights_invalid(self):
        weights = {name: 0 for name in CRITERIA_NAMES}
        valid, msg = validate_weights(weights)
        assert valid is False
        assert "short of 100" in msg

    def test_single_weight_at_100(self):
        weights = {name: 0 for name in CRITERIA_NAMES}
        weights['overage'] = 100
        valid, msg = validate_weights(weights)
        assert valid is True
        assert msg == ""


class TestGetRemainingBudget:
    """Tests for get_remaining_budget function."""

    def test_full_budget_returns_zero(self):
        assert get_remaining_budget(DEFAULT_WEIGHTS['Vendor']) == 0

    def test_empty_weights_returns_100(self):
        weights = {name: 0 for name in CRITERIA_NAMES}
        assert get_remaining_budget(weights) == 100

    def test_partial_weights(self):
        weights = {name: 5 for name in CRITERIA_NAMES}  # sum = 50
        assert get_remaining_budget(weights) == 50

    def test_over_budget_returns_negative(self):
        weights = {name: 11 for name in CRITERIA_NAMES}  # sum = 110
        assert get_remaining_budget(weights) == -10


class TestValidateThresholds:
    """Tests for validate_thresholds function."""

    def test_valid_thresholds(self):
        valid, msg = validate_thresholds({'A': 0.01, 'B': 0.03, 'C': 0.05})
        assert valid is True
        assert msg == ""

    def test_valid_default_vendor_thresholds(self):
        for criteria, thresholds in DEFAULT_THRESHOLDS['Vendor'].items():
            valid, msg = validate_thresholds(thresholds)
            assert valid is True, f"Failed for {criteria}: {msg}"

    def test_valid_default_seller_thresholds(self):
        for criteria, thresholds in DEFAULT_THRESHOLDS['Seller'].items():
            valid, msg = validate_thresholds(thresholds)
            assert valid is True, f"Failed for {criteria}: {msg}"

    def test_a_equals_b_rejected(self):
        valid, msg = validate_thresholds({'A': 0.01, 'B': 0.01, 'C': 0.05})
        assert valid is False
        assert "A" in msg and "B" in msg

    def test_b_equals_c_rejected(self):
        valid, msg = validate_thresholds({'A': 0.01, 'B': 0.05, 'C': 0.05})
        assert valid is False
        assert "B" in msg and "C" in msg

    def test_reversed_order_rejected(self):
        valid, msg = validate_thresholds({'A': 0.05, 'B': 0.03, 'C': 0.01})
        assert valid is False

    def test_missing_key_rejected(self):
        valid, msg = validate_thresholds({'A': 0.01, 'B': 0.03})
        assert valid is False
        assert "must contain keys" in msg

    def test_hours_based_valid(self):
        valid, msg = validate_thresholds({'A': 24, 'B': 48, 'C': 72})
        assert valid is True


class TestValidateTierBoundaries:
    """Tests for validate_tier_boundaries function."""

    def test_valid_default_boundaries(self):
        valid, msg = validate_tier_boundaries(DEFAULT_TIER_BOUNDARIES)
        assert valid is True
        assert msg == ""

    def test_a_equals_b_rejected(self):
        valid, msg = validate_tier_boundaries({'A': 95, 'B': 95, 'C': 60})
        assert valid is False
        assert "A" in msg and "B" in msg

    def test_b_equals_c_rejected(self):
        valid, msg = validate_tier_boundaries({'A': 95, 'B': 60, 'C': 60})
        assert valid is False
        assert "B" in msg and "C" in msg

    def test_reversed_order_rejected(self):
        valid, msg = validate_tier_boundaries({'A': 60, 'B': 80, 'C': 95})
        assert valid is False

    def test_missing_key_rejected(self):
        valid, msg = validate_tier_boundaries({'A': 95, 'B': 80})
        assert valid is False
        assert "must contain keys" in msg

    def test_valid_custom_boundaries(self):
        valid, msg = validate_tier_boundaries({'A': 90, 'B': 70, 'C': 50})
        assert valid is True
        assert msg == ""
