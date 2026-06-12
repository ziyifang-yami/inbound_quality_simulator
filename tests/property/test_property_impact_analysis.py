"""
Property-based tests for impact analysis correctness (Property 12).

**Validates: Requirements 7.1, 7.2**

Property 12: Impact Analysis Correctness
For any pair of scored DataFrames (baseline and current) sharing the same vendor_id set,
the Impact_Analyzer SHALL correctly identify ALL records whose tier differs between
baseline and current, produce accurate transition counts, and the sum of all transition
counts SHALL equal the total changed count.

Properties tested:
1. changed_count == len(changed_vendors)
2. upgrades + downgrades == changed_count
3. sum of all transition counts == changed_count
4. Every vendor in changed_vendors has a tier difference between baseline and current
5. No vendor NOT in changed_vendors has a tier difference
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from impact import analyze_impact


# --- Strategies ---

TIERS = ['A', 'B', 'C', 'D']


@st.composite
def paired_dataframes(draw):
    """
    Generate two DataFrames (baseline and current) with the same vendor_ids
    but potentially different tier assignments.

    Returns (baseline_df, current_df) both with 'vendor_id' and 'tier' columns.
    """
    # Generate between 1 and 50 unique vendor_ids
    n_vendors = draw(st.integers(min_value=1, max_value=50))
    vendor_ids = list(range(1, n_vendors + 1))

    # Generate tier assignments for baseline and current
    baseline_tiers = draw(
        st.lists(st.sampled_from(TIERS), min_size=n_vendors, max_size=n_vendors)
    )
    current_tiers = draw(
        st.lists(st.sampled_from(TIERS), min_size=n_vendors, max_size=n_vendors)
    )

    baseline_df = pd.DataFrame({
        'vendor_id': vendor_ids,
        'tier': baseline_tiers,
    })
    current_df = pd.DataFrame({
        'vendor_id': vendor_ids,
        'tier': current_tiers,
    })

    return baseline_df, current_df


# --- Property Tests ---


class TestImpactAnalysisCorrectness:
    """
    **Validates: Requirements 7.1, 7.2**

    Property 12: Impact Analysis Correctness
    Generate paired DataFrames with same vendor_ids but different tiers; verify
    changed_count matches, transition counts sum correctly, all changed vendors identified.
    """

    @given(data=paired_dataframes())
    @settings(max_examples=300, deadline=None)
    def test_changed_count_equals_len_changed_vendors(self, data):
        """
        Property: changed_count == len(changed_vendors).
        The reported count of changed vendors must equal the length of the
        changed_vendors list.
        """
        baseline_df, current_df = data
        result = analyze_impact(baseline_df, current_df)

        assert result['changed_count'] == len(result['changed_vendors']), (
            f"changed_count ({result['changed_count']}) != "
            f"len(changed_vendors) ({len(result['changed_vendors'])})"
        )

    @given(data=paired_dataframes())
    @settings(max_examples=300, deadline=None)
    def test_upgrades_plus_downgrades_equals_changed_count(self, data):
        """
        Property: upgrades + downgrades == changed_count.
        Every changed vendor must be either an upgrade or a downgrade (not 'same').
        """
        baseline_df, current_df = data
        result = analyze_impact(baseline_df, current_df)

        assert result['upgrades'] + result['downgrades'] == result['changed_count'], (
            f"upgrades ({result['upgrades']}) + downgrades ({result['downgrades']}) = "
            f"{result['upgrades'] + result['downgrades']} != "
            f"changed_count ({result['changed_count']})"
        )

    @given(data=paired_dataframes())
    @settings(max_examples=300, deadline=None)
    def test_transition_counts_sum_equals_changed_count(self, data):
        """
        Property: sum of all transition counts == changed_count.
        The total across all transition types (e.g., 'B→A': 5, 'C→D': 3)
        must equal the total number of changed vendors.
        """
        baseline_df, current_df = data
        result = analyze_impact(baseline_df, current_df)

        transition_sum = sum(result['transitions'].values())
        assert transition_sum == result['changed_count'], (
            f"sum(transitions) ({transition_sum}) != "
            f"changed_count ({result['changed_count']}). "
            f"Transitions: {result['transitions']}"
        )

    @given(data=paired_dataframes())
    @settings(max_examples=300, deadline=None)
    def test_every_changed_vendor_has_tier_difference(self, data):
        """
        Property: Every vendor in changed_vendors has a tier difference
        between baseline and current.
        """
        baseline_df, current_df = data
        result = analyze_impact(baseline_df, current_df)

        # Build lookup maps for baseline and current tiers
        baseline_map = dict(zip(baseline_df['vendor_id'], baseline_df['tier']))
        # Use original current tiers (before analyze_impact modifies current_df)
        current_map = dict(zip(current_df['vendor_id'], current_df['tier']))

        for vid in result['changed_vendors']:
            assert baseline_map[vid] != current_map[vid], (
                f"Vendor {vid} is in changed_vendors but has same tier: "
                f"baseline={baseline_map[vid]}, current={current_map[vid]}"
            )

    @given(data=paired_dataframes())
    @settings(max_examples=300, deadline=None)
    def test_no_unchanged_vendor_in_changed_list(self, data):
        """
        Property: No vendor NOT in changed_vendors has a tier difference.
        If a vendor's tier is the same in both baseline and current, it must
        NOT appear in the changed_vendors list.
        """
        baseline_df, current_df = data
        result = analyze_impact(baseline_df, current_df)

        # Build lookup maps
        baseline_map = dict(zip(baseline_df['vendor_id'], baseline_df['tier']))
        current_map = dict(zip(current_df['vendor_id'], current_df['tier']))

        changed_set = set(result['changed_vendors'])
        all_vendor_ids = set(baseline_df['vendor_id'])

        # Vendors NOT in changed_vendors must have the same tier
        unchanged_vendors = all_vendor_ids - changed_set
        for vid in unchanged_vendors:
            assert baseline_map[vid] == current_map[vid], (
                f"Vendor {vid} is NOT in changed_vendors but has different tiers: "
                f"baseline={baseline_map[vid]}, current={current_map[vid]}"
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
