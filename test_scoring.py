"""Unit tests for scoring.py — compute_grade and compute_scores."""

import pandas as pd
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from scoring import compute_grade, compute_scores, classify_tier
from config import CRITERIA_NAMES, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, DEFAULT_TIER_BOUNDARIES


class TestComputeGrade:
    """Tests for compute_grade function."""

    def test_rate_at_zero_returns_100(self):
        thresholds = {'A': 0.01, 'B': 0.03, 'C': 0.05}
        assert compute_grade(0.0, thresholds) == 100

    def test_rate_exactly_at_A_boundary_returns_100(self):
        thresholds = {'A': 0.01, 'B': 0.03, 'C': 0.05}
        assert compute_grade(0.01, thresholds) == 100

    def test_rate_just_above_A_returns_80(self):
        thresholds = {'A': 0.01, 'B': 0.03, 'C': 0.05}
        assert compute_grade(0.0100001, thresholds) == 80

    def test_rate_exactly_at_B_boundary_returns_80(self):
        thresholds = {'A': 0.01, 'B': 0.03, 'C': 0.05}
        assert compute_grade(0.03, thresholds) == 80

    def test_rate_just_above_B_returns_60(self):
        thresholds = {'A': 0.01, 'B': 0.03, 'C': 0.05}
        assert compute_grade(0.0300001, thresholds) == 60

    def test_rate_exactly_at_C_boundary_returns_60(self):
        thresholds = {'A': 0.01, 'B': 0.03, 'C': 0.05}
        assert compute_grade(0.05, thresholds) == 60

    def test_rate_above_C_returns_20(self):
        thresholds = {'A': 0.01, 'B': 0.03, 'C': 0.05}
        assert compute_grade(0.06, thresholds) == 20

    def test_responsiveness_hours_thresholds(self):
        thresholds = {'A': 24, 'B': 48, 'C': 72}
        assert compute_grade(12, thresholds) == 100
        assert compute_grade(24, thresholds) == 100
        assert compute_grade(36, thresholds) == 80
        assert compute_grade(48, thresholds) == 80
        assert compute_grade(60, thresholds) == 60
        assert compute_grade(72, thresholds) == 60
        assert compute_grade(100, thresholds) == 20

    def test_rate_with_zero_A_threshold(self):
        """UPC error has A=0.00, so only rate==0 gets 100."""
        thresholds = {'A': 0.00, 'B': 0.005, 'C': 0.01}
        assert compute_grade(0.0, thresholds) == 100
        assert compute_grade(0.001, thresholds) == 80


class TestComputeScores:
    """Tests for compute_scores function."""

    def _make_df(self, business_type='Vendor', rates=None):
        """Helper to create a single-row test DataFrame."""
        if rates is None:
            rates = {}
        row = {
            'warehouse_number': '001',
            'vendor_id': 1,
            'vendor_name': 'Test Vendor',
            'business_type': business_type,
            'team': 'Food',
            'qty_received': 1000,
        }
        # Set default rates to 0 (best possible)
        for criteria in CRITERIA_NAMES:
            if criteria == 'responsiveness':
                row['responsiveness_hours'] = rates.get('responsiveness', 0.0)
            else:
                row[f'{criteria}_rate'] = rates.get(criteria, 0.0)
        # Override with provided rates
        return pd.DataFrame([row])

    def test_perfect_vendor_scores_100(self):
        """All rates at 0 should give grade 100 for all criteria → total = 100."""
        df = self._make_df('Vendor')
        result = compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
        assert result['total_score'].iloc[0] == 100.0

    def test_worst_vendor_scores_20(self):
        """All rates far above C threshold → grade 20 for all → total = 20."""
        rates = {c: 1.0 for c in CRITERIA_NAMES[:-1]}
        rates['responsiveness'] = 200  # far above 72 hours
        df = self._make_df('Vendor', rates)
        result = compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
        assert result['total_score'].iloc[0] == 20.0

    def test_grade_columns_added(self):
        """compute_scores adds grade_{criteria} and total_score columns."""
        df = self._make_df('Vendor')
        result = compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
        for criteria in CRITERIA_NAMES:
            assert f'grade_{criteria}' in result.columns
        assert 'total_score' in result.columns

    def test_business_type_routing_vendor(self):
        """Vendor records use Vendor weights/thresholds."""
        # Set damage_rate just above Vendor's A threshold (0.005) but below Seller's A (0.01)
        df = self._make_df('Vendor', {'damage': 0.007})
        result = compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
        # Vendor damage threshold A=0.005, so 0.007 > A → grade 80
        assert result['grade_damage'].iloc[0] == 80

    def test_business_type_routing_seller(self):
        """Seller records use Seller weights/thresholds."""
        # damage_rate 0.007 — Seller's A threshold is 0.01, so 0.007 <= 0.01 → grade 100
        df = self._make_df('Seller', {'damage': 0.007})
        result = compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
        assert result['grade_damage'].iloc[0] == 100

    def test_zero_weight_criteria_excluded(self):
        """When a criteria weight is 0, it doesn't affect total score."""
        # Vendor's responsiveness weight = 0 by default
        # Set responsiveness hours to worst case, should not affect total
        rates = {'responsiveness': 200}  # worst grade = 20
        df = self._make_df('Vendor', rates)
        result = compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
        # All other rates are 0 (grade 100), responsiveness weight is 0
        # Total = sum of (100 * weight/100) for all non-zero weights = 100
        assert result['total_score'].iloc[0] == 100.0

    def test_mixed_business_types(self):
        """DataFrame with both Vendor and Seller records routes correctly."""
        vendor_row = {
            'warehouse_number': '001', 'vendor_id': 1,
            'vendor_name': 'Vendor A', 'business_type': 'Vendor',
            'team': 'Food', 'qty_received': 1000,
        }
        seller_row = {
            'warehouse_number': '002', 'vendor_id': 2,
            'vendor_name': 'Seller B', 'business_type': 'Seller',
            'team': 'Non-food', 'qty_received': 500,
        }
        for criteria in CRITERIA_NAMES:
            if criteria == 'responsiveness':
                vendor_row['responsiveness_hours'] = 0.0
                seller_row['responsiveness_hours'] = 0.0
            else:
                vendor_row[f'{criteria}_rate'] = 0.0
                seller_row[f'{criteria}_rate'] = 0.0

        df = pd.DataFrame([vendor_row, seller_row])
        result = compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
        # Both should be 100 with all rates at 0
        assert result['total_score'].iloc[0] == 100.0
        assert result['total_score'].iloc[1] == 100.0

    def test_weighted_score_calculation(self):
        """Verify total_score formula: sum(grade_i * weight_i / 100)."""
        # Set overage_rate above C threshold → grade 20
        # All others at 0 → grade 100
        # Vendor overage weight = 15
        # Expected: 20*15/100 + 100*85/100 = 3 + 85 = 88
        rates = {'overage': 0.5}  # far above C=0.03 → grade 20
        df = self._make_df('Vendor', rates)
        result = compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
        # Vendor weights sum to 100, overage=15, rest=85 (responsiveness=0, so effective rest=85)
        # grade_overage=20, all others=100
        # total = 20*15/100 + 100*85/100 = 3 + 85 = 88
        assert result['total_score'].iloc[0] == 88.0

    def test_original_df_not_modified(self):
        """compute_scores should not modify the input DataFrame."""
        df = self._make_df('Vendor')
        original_cols = list(df.columns)
        compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
        assert list(df.columns) == original_cols

    def test_tier_column_added(self):
        """compute_scores adds a 'tier' column to the output."""
        df = self._make_df('Vendor')
        result = compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
        assert 'tier' in result.columns

    def test_perfect_vendor_gets_tier_a(self):
        """All rates at 0 → total_score 100 → Tier A."""
        df = self._make_df('Vendor')
        result = compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
        assert result['tier'].iloc[0] == 'A'

    def test_worst_vendor_gets_tier_d(self):
        """All rates far above C → total_score 20 → Tier D."""
        rates = {c: 1.0 for c in CRITERIA_NAMES[:-1]}
        rates['responsiveness'] = 200
        df = self._make_df('Vendor', rates)
        result = compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
        assert result['tier'].iloc[0] == 'D'

    def test_custom_tier_boundaries(self):
        """compute_scores uses provided tier_boundaries instead of defaults."""
        # With default thresholds and all rates at 0, score = 100
        # Custom boundary A=101 means score 100 < 101, won't get A
        df = self._make_df('Vendor')
        custom_boundaries = {'A': 101, 'B': 99, 'C': 50}
        result = compute_scores(df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, tier_boundaries=custom_boundaries)
        assert result['tier'].iloc[0] == 'B'


class TestClassifyTier:
    """Tests for classify_tier function."""

    def test_score_at_a_boundary(self):
        """Score exactly at A boundary returns 'A'."""
        assert classify_tier(95.0, DEFAULT_TIER_BOUNDARIES) == 'A'

    def test_score_above_a_boundary(self):
        """Score above A boundary returns 'A'."""
        assert classify_tier(100.0, DEFAULT_TIER_BOUNDARIES) == 'A'

    def test_score_just_below_a_boundary(self):
        """Score just below A boundary returns 'B'."""
        assert classify_tier(94.9, DEFAULT_TIER_BOUNDARIES) == 'B'

    def test_score_at_b_boundary(self):
        """Score exactly at B boundary returns 'B'."""
        assert classify_tier(80.0, DEFAULT_TIER_BOUNDARIES) == 'B'

    def test_score_just_below_b_boundary(self):
        """Score just below B boundary returns 'C'."""
        assert classify_tier(79.9, DEFAULT_TIER_BOUNDARIES) == 'C'

    def test_score_at_c_boundary(self):
        """Score exactly at C boundary returns 'C'."""
        assert classify_tier(60.0, DEFAULT_TIER_BOUNDARIES) == 'C'

    def test_score_below_c_boundary(self):
        """Score below C boundary returns 'D'."""
        assert classify_tier(59.9, DEFAULT_TIER_BOUNDARIES) == 'D'

    def test_score_zero_returns_d(self):
        """Score of 0 returns 'D'."""
        assert classify_tier(0.0, DEFAULT_TIER_BOUNDARIES) == 'D'

    def test_custom_boundaries(self):
        """classify_tier works with custom boundaries."""
        boundaries = {'A': 90, 'B': 70, 'C': 50}
        assert classify_tier(95, boundaries) == 'A'
        assert classify_tier(90, boundaries) == 'A'
        assert classify_tier(89, boundaries) == 'B'
        assert classify_tier(70, boundaries) == 'B'
        assert classify_tier(69, boundaries) == 'C'
        assert classify_tier(50, boundaries) == 'C'
        assert classify_tier(49, boundaries) == 'D'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
