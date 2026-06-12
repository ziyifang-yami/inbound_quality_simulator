"""
Property-based tests for tier boundary validation (Property 11).

**Validates: Requirements 5.4**

Property 11: Tier Boundary Validation
For any set of tier boundary values {A, B, C}, validate_tier_boundaries SHALL return
valid=True if and only if A > B > C (higher tiers require higher scores).
Invalid orderings SHALL be rejected.
"""
import hypothesis
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from validators import validate_tier_boundaries


# Strategy: generate 3 distinct floats and sort descending to get valid A > B > C
@st.composite
def valid_tier_boundaries(draw):
    """Generate a valid tier boundary triple where A > B > C strictly."""
    values = draw(
        st.lists(
            st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            min_size=3,
            max_size=3,
            unique=True,
        )
    )
    values.sort(reverse=True)  # A > B > C
    return {'A': values[0], 'B': values[1], 'C': values[2]}


# Strategy: generate boundary triples where the strict ordering A > B > C is violated
@st.composite
def invalid_tier_boundaries(draw):
    """Generate an invalid tier boundary triple where A > B > C does NOT hold strictly."""
    a = draw(st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    b = draw(st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    c = draw(st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    # Ensure the ordering A > B > C does NOT hold
    assume(not (a > b > c))
    return {'A': a, 'B': b, 'C': c}


class TestProperty11TierBoundaryValidation:
    """
    Property 11: Tier Boundary Validation

    For any set of tier boundary values {A, B, C}, validate_tier_boundaries SHALL return
    valid=True if and only if A > B > C (higher tiers require higher scores).
    Invalid orderings SHALL be rejected.

    **Validates: Requirements 5.4**
    """

    @given(boundaries=valid_tier_boundaries())
    @settings(max_examples=200)
    def test_valid_boundaries_accepted(self, boundaries):
        """When A > B > C strictly, validate_tier_boundaries returns (True, "")."""
        is_valid, error_msg = validate_tier_boundaries(boundaries)
        assert is_valid is True, (
            f"Expected valid=True for boundaries {boundaries}, got error: {error_msg}"
        )
        assert error_msg == ""

    @given(boundaries=invalid_tier_boundaries())
    @settings(max_examples=200)
    def test_invalid_boundaries_rejected(self, boundaries):
        """When A > B > C does NOT hold strictly, validate_tier_boundaries returns (False, non-empty error)."""
        is_valid, error_msg = validate_tier_boundaries(boundaries)
        assert is_valid is False, (
            f"Expected valid=False for boundaries {boundaries} where A > B > C does not hold"
        )
        assert error_msg != "", (
            f"Expected non-empty error message for invalid boundaries {boundaries}"
        )

    @given(
        value=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_equal_a_and_b_rejected(self, value):
        """When A == B, the ordering A > B > C cannot hold, so validation rejects."""
        c = value - 1.0  # Ensure C < A == B
        boundaries = {'A': value, 'B': value, 'C': c}
        is_valid, error_msg = validate_tier_boundaries(boundaries)
        assert is_valid is False
        assert error_msg != ""

    @given(
        value=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_equal_b_and_c_rejected(self, value):
        """When B == C, the ordering A > B > C cannot hold, so validation rejects."""
        a = value + 1.0  # Ensure A > B == C
        boundaries = {'A': a, 'B': value, 'C': value}
        is_valid, error_msg = validate_tier_boundaries(boundaries)
        assert is_valid is False
        assert error_msg != ""
