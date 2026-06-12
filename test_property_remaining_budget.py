"""
Property-based tests for get_remaining_budget.

**Property 7: Remaining Weight Budget**
For any current weight configuration (a dict of integer values),
get_remaining_budget SHALL return exactly 100 minus the sum of all weight values.

**Validates: Requirements 3.3**
"""
import hypothesis
from hypothesis import given, settings
from hypothesis import strategies as st

from config import CRITERIA_NAMES
from validators import get_remaining_budget


# Strategy: generate a dictionary with CRITERIA_NAMES as keys and arbitrary integer values
weight_dicts = st.fixed_dictionaries(
    {name: st.integers(min_value=-200, max_value=200) for name in CRITERIA_NAMES}
)


@given(weights=weight_dicts)
@settings(max_examples=200)
def test_remaining_budget_equals_100_minus_sum(weights: dict[str, int]):
    """
    Property 7: For any weight dict, get_remaining_budget returns exactly
    100 - sum(weights.values()).

    **Validates: Requirements 3.3**
    """
    result = get_remaining_budget(weights)
    expected = 100 - sum(weights.values())
    assert result == expected, (
        f"get_remaining_budget returned {result}, expected {expected} "
        f"for weights summing to {sum(weights.values())}"
    )


@given(weights=st.fixed_dictionaries(
    {name: st.integers(min_value=0, max_value=100) for name in CRITERIA_NAMES}
))
@settings(max_examples=200)
def test_remaining_budget_valid_range_weights(weights: dict[str, int]):
    """
    Property 7 (constrained): For weight values in [0, 100], get_remaining_budget
    still returns exactly 100 - sum(weights.values()).

    **Validates: Requirements 3.3**
    """
    result = get_remaining_budget(weights)
    expected = 100 - sum(weights.values())
    assert result == expected


@given(
    subset_keys=st.lists(
        st.sampled_from(CRITERIA_NAMES),
        min_size=1,
        max_size=len(CRITERIA_NAMES),
        unique=True,
    ),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=1, max_size=10),
)
@settings(max_examples=200)
def test_remaining_budget_partial_dicts(subset_keys: list[str], values: list[int]):
    """
    Property 7 (partial): For partial weight dicts (subset of keys),
    get_remaining_budget returns exactly 100 - sum(values).

    **Validates: Requirements 3.3**
    """
    # Build a partial dict from subset of criteria names
    partial_weights = {
        key: values[i % len(values)] for i, key in enumerate(subset_keys)
    }
    result = get_remaining_budget(partial_weights)
    expected = 100 - sum(partial_weights.values())
    assert result == expected
