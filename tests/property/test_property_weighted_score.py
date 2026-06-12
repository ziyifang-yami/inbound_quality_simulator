"""
Property-based tests for weighted score calculation (Property 4).

**Validates: Requirements 2.2, 2.5**

Property 4: Weighted Score Calculation
For any array of 10 grades (each from {100, 80, 60, 20}) and any array of 10 weights
(each in [0, 100], summing to exactly 100), the total_score SHALL equal
Σ(grade_i × weight_i / 100), yielding a value in [20, 100].
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from scoring import compute_scores
from config import CRITERIA_NAMES, DEFAULT_THRESHOLDS


# --- Strategies ---

# Generate a single grade from the valid set
grade_strategy = st.sampled_from([100, 80, 60, 20])

# Generate 10 grades (one per criteria)
grades_strategy = st.lists(grade_strategy, min_size=10, max_size=10)


@st.composite
def weights_summing_to_100(draw):
    """
    Generate a list of 10 non-negative integers in [0, 100] that sum to exactly 100.

    Strategy: draw 9 values from a Dirichlet-like approach using sorted cutpoints,
    then compute the 10th as the remainder.
    """
    # Generate 9 sorted cut points in [0, 100]
    cuts = sorted(draw(st.lists(st.integers(min_value=0, max_value=100), min_size=9, max_size=9)))
    # Convert cut points to weights via differences
    weights = []
    prev = 0
    for c in cuts:
        weights.append(c - prev)
        prev = c
    weights.append(100 - prev)
    # All weights should be in [0, 100] by construction
    assert len(weights) == 10
    assert sum(weights) == 100
    assert all(0 <= w <= 100 for w in weights)
    return weights


def _rate_for_grade(grade: int, thresholds: dict) -> float:
    """
    Return a rate value that will produce the desired grade given the thresholds.

    Grade mapping:
      100 → rate <= A (use 0)
      80  → A < rate <= B (use midpoint between A and B)
      60  → B < rate <= C (use midpoint between B and C)
      20  → rate > C (use C + a margin)
    """
    a, b, c = thresholds['A'], thresholds['B'], thresholds['C']
    if grade == 100:
        return 0.0  # always <= A
    elif grade == 80:
        # Rate strictly above A but at or below B
        return (a + b) / 2.0 if b > a else a + 0.001
    elif grade == 60:
        # Rate strictly above B but at or below C
        return (b + c) / 2.0 if c > b else b + 0.001
    else:  # grade == 20
        # Rate strictly above C
        return c + (c * 0.5 if c > 0 else 1.0)


# --- Property Test ---

class TestWeightedScoreCalculation:
    """
    **Validates: Requirements 2.2, 2.5**

    Property 4: Weighted Score Calculation
    Generate 10 grades (each from {100,80,60,20}) × 10 weights (each [0,100], sum=100);
    total_score == Σ(grade_i × weight_i / 100) and result in [20, 100].
    """

    @given(
        grades=grades_strategy,
        weights=weights_summing_to_100(),
    )
    @settings(max_examples=200, deadline=None)
    def test_weighted_score_equals_formula_and_in_range(self, grades, weights):
        """
        For any 10 grades and 10 weights summing to 100,
        the computed total_score must equal Σ(grade_i * weight_i / 100)
        and the result must be in range [20, 100].
        """
        # Build weight dict for Vendor business type
        weight_dict = {
            'Vendor': {CRITERIA_NAMES[i]: weights[i] for i in range(10)},
            'Seller': {CRITERIA_NAMES[i]: weights[i] for i in range(10)},
        }

        # Use default Vendor thresholds to construct rates that produce desired grades
        thresholds_vendor = DEFAULT_THRESHOLDS['Vendor']

        # Build a single-row DataFrame with rates engineered to produce the target grades
        row = {
            'warehouse_number': '001',
            'vendor_id': 1,
            'vendor_name': 'Test Vendor',
            'business_type': 'Vendor',
            'team': 'Food',
            'qty_received': 1000,
        }

        for i, criteria in enumerate(CRITERIA_NAMES):
            target_grade = grades[i]
            rate = _rate_for_grade(target_grade, thresholds_vendor[criteria])
            if criteria == 'responsiveness':
                row['responsiveness_hours'] = rate
            else:
                row[f'{criteria}_rate'] = rate

        df = pd.DataFrame([row])

        # Compute scores using our generated weights
        result = compute_scores(df, weight_dict, DEFAULT_THRESHOLDS)

        # Verify each grade matches expected
        for i, criteria in enumerate(CRITERIA_NAMES):
            actual_grade = result[f'grade_{criteria}'].iloc[0]
            assert actual_grade == grades[i], (
                f"Grade mismatch for {criteria}: expected {grades[i]}, got {actual_grade}"
            )

        # Verify total_score == Σ(grade_i × weight_i / 100)
        expected_score = sum(grades[i] * weights[i] / 100.0 for i in range(10))
        actual_score = result['total_score'].iloc[0]
        assert abs(actual_score - expected_score) < 1e-9, (
            f"Score mismatch: expected {expected_score}, got {actual_score}"
        )

        # Verify total_score is in [20, 100]
        # The minimum possible score is when all grades are 20: 20 * 100/100 = 20
        # The maximum is when all grades are 100: 100 * 100/100 = 100
        assert 20.0 - 1e-9 <= actual_score <= 100.0 + 1e-9, (
            f"Score {actual_score} out of valid range [20, 100]"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
