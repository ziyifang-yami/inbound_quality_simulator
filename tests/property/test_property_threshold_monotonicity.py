"""
Property-based tests for threshold monotonicity validation (Property 9).

**Validates: Requirements 4.2, 4.3**

Property 9: Threshold Monotonicity Validation
For any set of threshold boundary values {A, B, C} for a criteria dimension,
validate_thresholds SHALL return valid=True if and only if A < B < C
(strict monotonic ordering). Violations SHALL be rejected with an error
identifying the conflicting boundary.
"""
import hypothesis
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from validators import validate_thresholds


# Strategy: generate three distinct sorted floats to form a valid A < B < C triple
valid_threshold_triples = st.lists(
    st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    min_size=3,
    max_size=3,
    unique=True,
).map(sorted).map(lambda vals: {'A': vals[0], 'B': vals[1], 'C': vals[2]})


# Strategy: generate triples where A >= B (violates first monotonicity constraint)
invalid_a_ge_b_triples = st.tuples(
    st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
).filter(lambda t: t[0] >= t[1]).map(lambda t: {'A': t[0], 'B': t[1], 'C': t[2]})


# Strategy: generate triples where A < B but B >= C (violates second constraint)
invalid_b_ge_c_triples = st.tuples(
    st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
).filter(lambda t: t[0] < t[1] and t[1] >= t[2]).map(lambda t: {'A': t[0], 'B': t[1], 'C': t[2]})


class TestThresholdMonotonicity:
    """Property 9: Threshold Monotonicity Validation."""

    @given(thresholds=valid_threshold_triples)
    @settings(max_examples=200)
    def test_valid_monotonic_triples_accepted(self, thresholds):
        """
        For any triple where A < B < C strictly, validate_thresholds
        returns (True, "").

        **Validates: Requirements 4.2, 4.3**
        """
        is_valid, error_msg = validate_thresholds(thresholds)
        assert is_valid is True, (
            f"Expected valid=True for monotonic triple {thresholds}, "
            f"but got error: {error_msg}"
        )
        assert error_msg == ""

    @given(thresholds=invalid_a_ge_b_triples)
    @settings(max_examples=200)
    def test_a_ge_b_violation_rejected(self, thresholds):
        """
        For any triple where A >= B, validate_thresholds returns (False, error)
        with an error identifying the A/B boundary conflict.

        **Validates: Requirements 4.2, 4.3**
        """
        is_valid, error_msg = validate_thresholds(thresholds)
        assert is_valid is False, (
            f"Expected valid=False for A >= B triple {thresholds}, "
            f"but got valid=True"
        )
        assert error_msg != "", "Error message should not be empty on rejection"

    @given(thresholds=invalid_b_ge_c_triples)
    @settings(max_examples=200)
    def test_b_ge_c_violation_rejected(self, thresholds):
        """
        For any triple where A < B but B >= C, validate_thresholds returns
        (False, error) with an error identifying the B/C boundary conflict.

        **Validates: Requirements 4.2, 4.3**
        """
        is_valid, error_msg = validate_thresholds(thresholds)
        assert is_valid is False, (
            f"Expected valid=False for B >= C triple {thresholds}, "
            f"but got valid=True"
        )
        assert error_msg != "", "Error message should not be empty on rejection"

    @given(
        a=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        b=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        c=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=300)
    def test_validate_thresholds_iff_strictly_monotonic(self, a, b, c):
        """
        For any triple {A, B, C}, validate_thresholds returns True if and only if
        A < B < C (strict monotonic ordering).

        This is the complete biconditional property: valid ↔ (A < B < C).

        **Validates: Requirements 4.2, 4.3**
        """
        thresholds = {'A': a, 'B': b, 'C': c}
        is_valid, error_msg = validate_thresholds(thresholds)

        expected_valid = (a < b) and (b < c)

        assert is_valid == expected_valid, (
            f"For thresholds A={a}, B={b}, C={c}: "
            f"expected valid={expected_valid}, got valid={is_valid}. "
            f"Error: {error_msg}"
        )

        if is_valid:
            assert error_msg == "", (
                f"Valid thresholds should have empty error, got: {error_msg}"
            )
        else:
            assert error_msg != "", (
                f"Invalid thresholds A={a}, B={b}, C={c} should have "
                f"non-empty error message"
            )
