"""
Property-based tests for grade computation determinism.

**Property 3: Grade Computation Determinism**
For any rate value (float >= 0) and any valid threshold configuration (A < B < C),
compute_grade always returns exactly one value from {100, 80, 60, 20}, and the
returned grade correctly corresponds to which threshold interval the rate falls within.

**Validates: Requirements 2.1**
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from hypothesis import given, strategies as st, settings
from scoring import compute_grade


# Strategy: generate 3 sorted distinct positive floats for thresholds A < B < C
def valid_thresholds_strategy():
    """Generate valid thresholds dict with A < B < C (strictly increasing)."""
    return st.tuples(
        st.floats(min_value=0.0001, max_value=1000.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.0001, max_value=1000.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.0001, max_value=1000.0, allow_nan=False, allow_infinity=False),
    ).filter(
        lambda t: t[0] < t[1] < t[2]
    ).map(
        lambda t: {'A': t[0], 'B': t[1], 'C': t[2]}
    )


# Strategy: generate a non-negative float rate
rate_strategy = st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False)


@given(rate=rate_strategy, thresholds=valid_thresholds_strategy())
@settings(max_examples=500)
def test_grade_returns_valid_value(rate, thresholds):
    """
    Property 3: compute_grade always returns exactly one of {100, 80, 60, 20}.

    **Validates: Requirements 2.1**
    """
    grade = compute_grade(rate, thresholds)
    assert grade in {100, 80, 60, 20}, (
        f"compute_grade({rate}, {thresholds}) returned {grade}, "
        f"expected one of {{100, 80, 60, 20}}"
    )


@given(rate=rate_strategy, thresholds=valid_thresholds_strategy())
@settings(max_examples=500)
def test_grade_matches_correct_interval(rate, thresholds):
    """
    Property 3: The returned grade correctly corresponds to the threshold interval.

    - rate <= A → 100
    - A < rate <= B → 80
    - B < rate <= C → 60
    - rate > C → 20

    **Validates: Requirements 2.1**
    """
    grade = compute_grade(rate, thresholds)
    A, B, C = thresholds['A'], thresholds['B'], thresholds['C']

    if rate <= A:
        expected = 100
    elif rate <= B:
        expected = 80
    elif rate <= C:
        expected = 60
    else:
        expected = 20

    assert grade == expected, (
        f"compute_grade({rate}, {thresholds}) returned {grade}, "
        f"expected {expected} for interval check "
        f"(A={A}, B={B}, C={C})"
    )
