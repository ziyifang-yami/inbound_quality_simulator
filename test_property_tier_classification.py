"""
Property-based tests for tier classification correctness (Property 10).

**Validates: Requirements 5.1, 5.3**

Property 10: Tier Classification Correctness
For any total score (float in [0, 100]) and any valid tier boundary configuration
(A > B > C), classify_tier SHALL assign exactly one tier, and the assignment SHALL
be consistent: score >= A → Tier A, B <= score < A → Tier B, C <= score < B → Tier C,
score < C → Tier D.
"""
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from scoring import classify_tier


# Strategy: generate valid tier boundaries where A > B > C, each in [0, 100]
@st.composite
def valid_tier_boundaries(draw):
    """Generate a valid tier boundary triple where A > B > C strictly, all in [0, 100]."""
    values = draw(
        st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=3,
            max_size=3,
            unique=True,
        )
    )
    values.sort(reverse=True)  # A > B > C
    return {'A': values[0], 'B': values[1], 'C': values[2]}


# Strategy: generate a score in [0, 100] paired with valid boundaries
@st.composite
def score_and_boundaries(draw):
    """Generate a random score in [0, 100] and valid tier boundaries (A > B > C)."""
    score = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    boundaries = draw(valid_tier_boundaries())
    return score, boundaries


class TestProperty10TierClassificationCorrectness:
    """
    Property 10: Tier Classification Correctness

    For any total score (float in [0, 100]) and any valid tier boundary configuration
    (A > B > C), classify_tier SHALL assign exactly one tier, and the assignment SHALL
    be consistent with boundary intervals.

    **Validates: Requirements 5.1, 5.3**
    """

    @given(data=score_and_boundaries())
    @settings(max_examples=500)
    def test_returns_exactly_one_valid_tier(self, data):
        """classify_tier always returns exactly one of {'A', 'B', 'C', 'D'}."""
        score, boundaries = data
        result = classify_tier(score, boundaries)
        assert result in {'A', 'B', 'C', 'D'}, (
            f"classify_tier({score}, {boundaries}) returned '{result}', "
            f"expected one of {{'A', 'B', 'C', 'D'}}"
        )

    @given(data=score_and_boundaries())
    @settings(max_examples=500)
    def test_tier_consistent_with_boundaries(self, data):
        """The returned tier is correct for the score/boundary combination."""
        score, boundaries = data
        result = classify_tier(score, boundaries)

        if score >= boundaries['A']:
            expected = 'A'
        elif score >= boundaries['B']:
            expected = 'B'
        elif score >= boundaries['C']:
            expected = 'C'
        else:
            expected = 'D'

        assert result == expected, (
            f"classify_tier({score}, {boundaries}) returned '{result}', "
            f"but expected '{expected}' based on boundary intervals"
        )

    @given(boundaries=valid_tier_boundaries())
    @settings(max_examples=200)
    def test_score_at_boundary_a_returns_tier_a(self, boundaries):
        """A score exactly at boundary A should classify as Tier A."""
        score = boundaries['A']
        result = classify_tier(score, boundaries)
        assert result == 'A', (
            f"Score {score} == boundary A ({boundaries['A']}) should be Tier A, got '{result}'"
        )

    @given(boundaries=valid_tier_boundaries())
    @settings(max_examples=200)
    def test_score_at_boundary_b_returns_tier_b(self, boundaries):
        """A score exactly at boundary B (but below A) should classify as Tier B."""
        score = boundaries['B']
        # B < A is guaranteed by our strategy
        result = classify_tier(score, boundaries)
        assert result == 'B', (
            f"Score {score} == boundary B ({boundaries['B']}) should be Tier B, got '{result}'"
        )

    @given(boundaries=valid_tier_boundaries())
    @settings(max_examples=200)
    def test_score_at_boundary_c_returns_tier_c(self, boundaries):
        """A score exactly at boundary C (but below B) should classify as Tier C."""
        score = boundaries['C']
        # C < B is guaranteed by our strategy
        result = classify_tier(score, boundaries)
        assert result == 'C', (
            f"Score {score} == boundary C ({boundaries['C']}) should be Tier C, got '{result}'"
        )

    @given(boundaries=valid_tier_boundaries())
    @settings(max_examples=200)
    def test_score_zero_classified_correctly(self, boundaries):
        """A score of 0 should be classified based on whether 0 >= C boundary."""
        score = 0.0
        result = classify_tier(score, boundaries)
        if score >= boundaries['A']:
            assert result == 'A'
        elif score >= boundaries['B']:
            assert result == 'B'
        elif score >= boundaries['C']:
            assert result == 'C'
        else:
            assert result == 'D'

    @given(boundaries=valid_tier_boundaries())
    @settings(max_examples=200)
    def test_score_100_always_tier_a(self, boundaries):
        """A score of 100 should always be Tier A since boundaries are in [0, 100]."""
        score = 100.0
        result = classify_tier(score, boundaries)
        assert result == 'A', (
            f"Score 100.0 should always be Tier A when boundaries are in [0, 100], "
            f"got '{result}' with boundaries {boundaries}"
        )
