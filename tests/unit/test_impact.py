"""
Unit tests for the Impact Analyzer module.
"""

import pandas as pd
import pytest

from impact import analyze_impact, _classify_direction, TIER_RANK


class TestClassifyDirection:
    """Tests for the _classify_direction helper."""

    def test_same_tier(self):
        assert _classify_direction('A', 'A') == 'same'
        assert _classify_direction('B', 'B') == 'same'
        assert _classify_direction('C', 'C') == 'same'
        assert _classify_direction('D', 'D') == 'same'

    def test_upgrade(self):
        # Moving to a better (lower rank) tier is an upgrade
        assert _classify_direction('B', 'A') == 'upgrade'
        assert _classify_direction('C', 'A') == 'upgrade'
        assert _classify_direction('C', 'B') == 'upgrade'
        assert _classify_direction('D', 'A') == 'upgrade'
        assert _classify_direction('D', 'B') == 'upgrade'
        assert _classify_direction('D', 'C') == 'upgrade'

    def test_downgrade(self):
        # Moving to a worse (higher rank) tier is a downgrade
        assert _classify_direction('A', 'B') == 'downgrade'
        assert _classify_direction('A', 'C') == 'downgrade'
        assert _classify_direction('A', 'D') == 'downgrade'
        assert _classify_direction('B', 'C') == 'downgrade'
        assert _classify_direction('B', 'D') == 'downgrade'
        assert _classify_direction('C', 'D') == 'downgrade'


class TestAnalyzeImpact:
    """Tests for the analyze_impact function."""

    def _make_df(self, vendor_ids, tiers):
        """Helper to create a minimal scored DataFrame."""
        return pd.DataFrame({
            'vendor_id': vendor_ids,
            'tier': tiers,
        })

    def test_no_changes(self):
        """All vendors stay in the same tier."""
        baseline = self._make_df([1, 2, 3], ['A', 'B', 'C'])
        current = self._make_df([1, 2, 3], ['A', 'B', 'C'])

        result = analyze_impact(baseline, current)

        assert result['changed_count'] == 0
        assert result['upgrades'] == 0
        assert result['downgrades'] == 0
        assert result['transitions'] == {}
        assert result['changed_vendors'] == []

        # Check in-place columns
        assert list(current['baseline_tier']) == ['A', 'B', 'C']
        assert list(current['tier_changed']) == [False, False, False]
        assert list(current['tier_direction']) == ['same', 'same', 'same']

    def test_all_upgrades(self):
        """All vendors upgrade."""
        baseline = self._make_df([1, 2, 3], ['B', 'C', 'D'])
        current = self._make_df([1, 2, 3], ['A', 'B', 'C'])

        result = analyze_impact(baseline, current)

        assert result['changed_count'] == 3
        assert result['upgrades'] == 3
        assert result['downgrades'] == 0
        assert result['transitions'] == {'B→A': 1, 'C→B': 1, 'D→C': 1}
        assert sorted(result['changed_vendors']) == [1, 2, 3]

    def test_all_downgrades(self):
        """All vendors downgrade."""
        baseline = self._make_df([1, 2, 3], ['A', 'B', 'C'])
        current = self._make_df([1, 2, 3], ['B', 'C', 'D'])

        result = analyze_impact(baseline, current)

        assert result['changed_count'] == 3
        assert result['upgrades'] == 0
        assert result['downgrades'] == 3
        assert result['transitions'] == {'A→B': 1, 'B→C': 1, 'C→D': 1}
        assert sorted(result['changed_vendors']) == [1, 2, 3]

    def test_mixed_changes(self):
        """Mix of upgrades, downgrades, and unchanged."""
        baseline = self._make_df([1, 2, 3, 4, 5], ['A', 'B', 'C', 'D', 'B'])
        current = self._make_df([1, 2, 3, 4, 5], ['A', 'A', 'D', 'C', 'B'])

        result = analyze_impact(baseline, current)

        assert result['changed_count'] == 3
        assert result['upgrades'] == 2  # vendor 2: B→A, vendor 4: D→C
        assert result['downgrades'] == 1  # vendor 3: C→D
        assert result['transitions'] == {'B→A': 1, 'C→D': 1, 'D→C': 1}
        assert sorted(result['changed_vendors']) == [2, 3, 4]

        # Check specific in-place values
        assert current.loc[current['vendor_id'] == 1, 'tier_direction'].iloc[0] == 'same'
        assert current.loc[current['vendor_id'] == 2, 'tier_direction'].iloc[0] == 'upgrade'
        assert current.loc[current['vendor_id'] == 3, 'tier_direction'].iloc[0] == 'downgrade'
        assert current.loc[current['vendor_id'] == 4, 'tier_direction'].iloc[0] == 'upgrade'
        assert current.loc[current['vendor_id'] == 5, 'tier_direction'].iloc[0] == 'same'

    def test_multiple_same_transition(self):
        """Multiple vendors with the same transition type."""
        baseline = self._make_df([1, 2, 3, 4], ['B', 'B', 'B', 'C'])
        current = self._make_df([1, 2, 3, 4], ['A', 'A', 'A', 'C'])

        result = analyze_impact(baseline, current)

        assert result['changed_count'] == 3
        assert result['upgrades'] == 3
        assert result['downgrades'] == 0
        assert result['transitions'] == {'B→A': 3}
        assert sorted(result['changed_vendors']) == [1, 2, 3]

    def test_inplace_columns_added(self):
        """Verify that baseline_tier, tier_changed, tier_direction are added in-place."""
        baseline = self._make_df([10, 20], ['A', 'C'])
        current = self._make_df([10, 20], ['B', 'A'])

        analyze_impact(baseline, current)

        assert 'baseline_tier' in current.columns
        assert 'tier_changed' in current.columns
        assert 'tier_direction' in current.columns
        assert current.loc[current['vendor_id'] == 10, 'baseline_tier'].iloc[0] == 'A'
        assert current.loc[current['vendor_id'] == 20, 'baseline_tier'].iloc[0] == 'C'

    def test_single_vendor(self):
        """Edge case: single vendor."""
        baseline = self._make_df([99], ['D'])
        current = self._make_df([99], ['A'])

        result = analyze_impact(baseline, current)

        assert result['changed_count'] == 1
        assert result['upgrades'] == 1
        assert result['downgrades'] == 0
        assert result['transitions'] == {'D→A': 1}
        assert result['changed_vendors'] == [99]


class TestTierRank:
    """Tests for the TIER_RANK ordering."""

    def test_ordering(self):
        assert TIER_RANK['A'] < TIER_RANK['B']
        assert TIER_RANK['B'] < TIER_RANK['C']
        assert TIER_RANK['C'] < TIER_RANK['D']

    def test_all_tiers_present(self):
        assert set(TIER_RANK.keys()) == {'A', 'B', 'C', 'D'}
