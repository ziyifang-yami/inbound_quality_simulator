"""
Property-based tests for weight validation (Property 6: Weight Sum Constraint).

**Validates: Requirements 3.2, 3.4**

Property 6: Weight Sum Constraint Validation
For any set of 10 integer weight values, validate_weights SHALL return valid=True
if and only if all values are in [0, 100] AND their sum equals exactly 100.
All other combinations SHALL be rejected.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypothesis import given, assume, settings
from hypothesis import strategies as st

from validators import validate_weights
from config import CRITERIA_NAMES


# Strategy: generate a dict mapping each of the 10 CRITERIA_NAMES to an integer
weight_vector_strategy = st.fixed_dictionaries(
    {name: st.integers(min_value=-50, max_value=150) for name in CRITERIA_NAMES}
)

# Strategy: generate a valid weight vector (all in [0,100], sum == 100)
# We generate 9 values in [0, 100] and compute the 10th to make sum == 100
def valid_weight_strategy():
    """Generate weight dicts guaranteed to have all values in [0,100] and sum == 100."""
    @st.composite
    def _build(draw):
        # Draw 9 values in [0, 100]
        values = [draw(st.integers(min_value=0, max_value=100)) for _ in range(9)]
        tenth = 100 - sum(values)
        # Only valid if the 10th value is also in [0, 100]
        assume(0 <= tenth <= 100)
        all_values = values + [tenth]
        return dict(zip(CRITERIA_NAMES, all_values))
    return _build()


class TestWeightSumConstraintProperty:
    """
    Property 6: Weight Sum Constraint Validation

    **Validates: Requirements 3.2, 3.4**
    """

    @given(weights=weight_vector_strategy)
    @settings(max_examples=200)
    def test_validate_weights_true_iff_valid(self, weights: dict):
        """
        For any 10-element integer weight dict:
        validate_weights returns (True, "") iff all values in [0,100] AND sum == 100.
        Otherwise returns (False, non-empty error message).

        **Validates: Requirements 3.2, 3.4**
        """
        all_in_range = all(0 <= v <= 100 for v in weights.values())
        sum_is_100 = sum(weights.values()) == 100

        is_valid, error_msg = validate_weights(weights)

        if all_in_range and sum_is_100:
            assert is_valid is True, (
                f"Expected valid=True for weights summing to {sum(weights.values())} "
                f"with all in range, but got False: {error_msg}"
            )
            assert error_msg == "", (
                f"Expected empty error message for valid weights, got: {error_msg}"
            )
        else:
            assert is_valid is False, (
                f"Expected valid=False for weights with all_in_range={all_in_range}, "
                f"sum={sum(weights.values())}, but got True"
            )
            assert error_msg != "", (
                "Expected non-empty error message for invalid weights"
            )

    @given(weights=valid_weight_strategy())
    @settings(max_examples=100)
    def test_valid_weights_always_accepted(self, weights: dict):
        """
        For any weight dict where all values are in [0,100] and sum == 100,
        validate_weights must return (True, "").

        **Validates: Requirements 3.2, 3.4**
        """
        is_valid, error_msg = validate_weights(weights)
        assert is_valid is True, (
            f"Valid weights rejected: sum={sum(weights.values())}, "
            f"values={list(weights.values())}, error={error_msg}"
        )
        assert error_msg == ""

    @given(weights=st.fixed_dictionaries(
        {name: st.integers(min_value=0, max_value=100) for name in CRITERIA_NAMES}
    ))
    @settings(max_examples=200)
    def test_invalid_sum_always_rejected(self, weights: dict):
        """
        For any weight dict where sum != 100 (even if all values in range),
        validate_weights must return (False, non-empty error).

        **Validates: Requirements 3.2, 3.4**
        """
        assume(sum(weights.values()) != 100)

        is_valid, error_msg = validate_weights(weights)
        assert is_valid is False, (
            f"Weights with sum={sum(weights.values())} should be rejected"
        )
        assert error_msg != ""

    @given(weights=weight_vector_strategy)
    @settings(max_examples=200)
    def test_out_of_range_always_rejected(self, weights: dict):
        """
        For any weight dict where at least one value is outside [0,100],
        validate_weights must return (False, non-empty error).

        **Validates: Requirements 3.2, 3.4**
        """
        assume(any(v < 0 or v > 100 for v in weights.values()))

        is_valid, error_msg = validate_weights(weights)
        assert is_valid is False, (
            f"Weights with out-of-range values should be rejected: "
            f"{[(k, v) for k, v in weights.items() if v < 0 or v > 100]}"
        )
        assert error_msg != ""
