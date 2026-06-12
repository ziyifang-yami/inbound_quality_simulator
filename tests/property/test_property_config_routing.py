"""
Property-based tests for business-type config routing (Property 5).

**Validates: Requirements 2.3, 2.4**

Property 5: Business-Type Config Routing
For any record with a given business_type (Vendor or Seller), the Scoring_Engine
SHALL use the weight configuration AND threshold configuration corresponding to
that business_type. A Vendor record SHALL never be scored with Seller
weights/thresholds, and vice versa.

Key property: changing only the Vendor config should only affect Vendor records'
scores, and vice versa.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from scoring import compute_scores, compute_grade
from config import CRITERIA_NAMES


# --- Strategies ---


@st.composite
def weights_summing_to_100(draw):
    """
    Generate a dict of 10 criteria weights (non-negative integers) summing to exactly 100.
    """
    cuts = sorted(draw(st.lists(st.integers(min_value=0, max_value=100), min_size=9, max_size=9)))
    weights = []
    prev = 0
    for c in cuts:
        weights.append(c - prev)
        prev = c
    weights.append(100 - prev)
    assert len(weights) == 10
    assert sum(weights) == 100
    assert all(0 <= w <= 100 for w in weights)
    return {CRITERIA_NAMES[i]: weights[i] for i in range(10)}


@st.composite
def valid_thresholds(draw):
    """
    Generate a valid threshold config for all 10 criteria with A < B < C ordering.
    Uses small float values for rate-based criteria and larger values for responsiveness.
    """
    thresholds = {}
    for criteria in CRITERIA_NAMES:
        if criteria == 'responsiveness':
            # Hours-based: generate A < B < C in range [1, 168]
            a = draw(st.integers(min_value=1, max_value=50))
            b = draw(st.integers(min_value=a + 1, max_value=100))
            c = draw(st.integers(min_value=b + 1, max_value=168))
        else:
            # Rate-based: generate A < B < C in range [0, 1]
            a = draw(st.floats(min_value=0.0, max_value=0.3, allow_nan=False, allow_infinity=False))
            b = draw(st.floats(min_value=a + 0.001, max_value=0.6, allow_nan=False, allow_infinity=False))
            c = draw(st.floats(min_value=b + 0.001, max_value=1.0, allow_nan=False, allow_infinity=False))
        thresholds[criteria] = {'A': a, 'B': b, 'C': c}
    return thresholds


@st.composite
def two_distinct_weight_configs(draw):
    """
    Generate two weight configs that differ in at least one criteria value.
    """
    vendor_weights = draw(weights_summing_to_100())
    seller_weights = draw(weights_summing_to_100())
    # Ensure they are actually distinct (at least one value differs)
    assume(vendor_weights != seller_weights)
    return vendor_weights, seller_weights


@st.composite
def two_distinct_threshold_configs(draw):
    """
    Generate two threshold configs that differ in at least one criteria boundary.
    """
    vendor_thresholds = draw(valid_thresholds())
    seller_thresholds = draw(valid_thresholds())
    # Ensure they are actually distinct
    assume(vendor_thresholds != seller_thresholds)
    return vendor_thresholds, seller_thresholds


def _build_record(business_type: str, vendor_id: int) -> dict:
    """
    Build a single record with fixed rate values for deterministic testing.
    Uses mid-range rates that will produce different grades under different thresholds.
    """
    row = {
        'warehouse_number': '001',
        'vendor_id': vendor_id,
        'vendor_name': f'Test {business_type} {vendor_id}',
        'business_type': business_type,
        'team': 'Food',
        'qty_received': 1000,
    }
    # Use fixed rate values in a range likely to hit different grade boundaries
    # across varied threshold configs
    rates = [0.008, 0.012, 0.004, 0.015, 0.025, 0.009, 0.011, 0.008, 0.012, 36.0]
    for i, criteria in enumerate(CRITERIA_NAMES):
        if criteria == 'responsiveness':
            row['responsiveness_hours'] = rates[i]
        else:
            row[f'{criteria}_rate'] = rates[i]
    return row


# --- Property Tests ---


class TestBusinessTypeConfigRouting:
    """
    **Validates: Requirements 2.3, 2.4**

    Property 5: Business-Type Config Routing
    Generate mixed-type records with distinct Vendor/Seller weight and threshold configs;
    verify each record scored with its own business_type's config only.
    """

    @given(
        weight_configs=two_distinct_weight_configs(),
        threshold_configs=two_distinct_threshold_configs(),
    )
    @settings(max_examples=200, deadline=None)
    def test_vendor_scored_with_vendor_config_only(self, weight_configs, threshold_configs):
        """
        Changing only the Seller config should NOT affect Vendor records' scores.
        Each Vendor record must be scored using Vendor weights and thresholds exclusively.
        """
        vendor_weights, seller_weights = weight_configs
        vendor_thresholds, seller_thresholds = threshold_configs

        # Build a DataFrame with both Vendor and Seller records
        vendor_record = _build_record('Vendor', vendor_id=1)
        seller_record = _build_record('Seller', vendor_id=2)
        df = pd.DataFrame([vendor_record, seller_record])

        # Score with config set A: use vendor_weights/vendor_thresholds for Vendor,
        # and seller_weights/seller_thresholds for Seller
        weights_a = {'Vendor': vendor_weights, 'Seller': seller_weights}
        thresholds_a = {'Vendor': vendor_thresholds, 'Seller': seller_thresholds}
        result_a = compute_scores(df, weights_a, thresholds_a)

        # Score with config set B: SAME vendor config, but DIFFERENT seller config
        # (swap seller weights/thresholds with vendor's to make them different)
        weights_b = {'Vendor': vendor_weights, 'Seller': vendor_weights}
        thresholds_b = {'Vendor': vendor_thresholds, 'Seller': vendor_thresholds}
        result_b = compute_scores(df, weights_b, thresholds_b)

        # Vendor record scores should be IDENTICAL in both runs
        vendor_row_a = result_a[result_a['business_type'] == 'Vendor'].iloc[0]
        vendor_row_b = result_b[result_b['business_type'] == 'Vendor'].iloc[0]

        assert vendor_row_a['total_score'] == vendor_row_b['total_score'], (
            f"Vendor score changed when only Seller config changed: "
            f"{vendor_row_a['total_score']} vs {vendor_row_b['total_score']}"
        )

        for criteria in CRITERIA_NAMES:
            assert vendor_row_a[f'grade_{criteria}'] == vendor_row_b[f'grade_{criteria}'], (
                f"Vendor grade for {criteria} changed when only Seller config changed"
            )

    @given(
        weight_configs=two_distinct_weight_configs(),
        threshold_configs=two_distinct_threshold_configs(),
    )
    @settings(max_examples=200, deadline=None)
    def test_seller_scored_with_seller_config_only(self, weight_configs, threshold_configs):
        """
        Changing only the Vendor config should NOT affect Seller records' scores.
        Each Seller record must be scored using Seller weights and thresholds exclusively.
        """
        vendor_weights, seller_weights = weight_configs
        vendor_thresholds, seller_thresholds = threshold_configs

        # Build a DataFrame with both Vendor and Seller records
        vendor_record = _build_record('Vendor', vendor_id=1)
        seller_record = _build_record('Seller', vendor_id=2)
        df = pd.DataFrame([vendor_record, seller_record])

        # Score with config set A
        weights_a = {'Vendor': vendor_weights, 'Seller': seller_weights}
        thresholds_a = {'Vendor': vendor_thresholds, 'Seller': seller_thresholds}
        result_a = compute_scores(df, weights_a, thresholds_a)

        # Score with config set B: SAME seller config, but DIFFERENT vendor config
        weights_b = {'Vendor': seller_weights, 'Seller': seller_weights}
        thresholds_b = {'Vendor': seller_thresholds, 'Seller': seller_thresholds}
        result_b = compute_scores(df, weights_b, thresholds_b)

        # Seller record scores should be IDENTICAL in both runs
        seller_row_a = result_a[result_a['business_type'] == 'Seller'].iloc[0]
        seller_row_b = result_b[result_b['business_type'] == 'Seller'].iloc[0]

        assert seller_row_a['total_score'] == seller_row_b['total_score'], (
            f"Seller score changed when only Vendor config changed: "
            f"{seller_row_a['total_score']} vs {seller_row_b['total_score']}"
        )

        for criteria in CRITERIA_NAMES:
            assert seller_row_a[f'grade_{criteria}'] == seller_row_b[f'grade_{criteria}'], (
                f"Seller grade for {criteria} changed when only Vendor config changed"
            )

    @given(
        weight_configs=two_distinct_weight_configs(),
        threshold_configs=two_distinct_threshold_configs(),
    )
    @settings(max_examples=200, deadline=None)
    def test_each_record_uses_own_business_type_config(self, weight_configs, threshold_configs):
        """
        Verify each record is scored using its own business_type's config by
        scoring a single record in isolation and comparing with mixed-DataFrame scoring.
        """
        vendor_weights, seller_weights = weight_configs
        vendor_thresholds, seller_thresholds = threshold_configs

        weights = {'Vendor': vendor_weights, 'Seller': seller_weights}
        thresholds = {'Vendor': vendor_thresholds, 'Seller': seller_thresholds}

        # Build mixed DataFrame
        vendor_record = _build_record('Vendor', vendor_id=1)
        seller_record = _build_record('Seller', vendor_id=2)
        mixed_df = pd.DataFrame([vendor_record, seller_record])

        # Score mixed DataFrame
        mixed_result = compute_scores(mixed_df, weights, thresholds)

        # Score Vendor record alone
        vendor_only_df = pd.DataFrame([vendor_record])
        vendor_only_result = compute_scores(vendor_only_df, weights, thresholds)

        # Score Seller record alone
        seller_only_df = pd.DataFrame([seller_record])
        seller_only_result = compute_scores(seller_only_df, weights, thresholds)

        # Vendor scores in mixed vs alone should be identical
        mixed_vendor = mixed_result[mixed_result['business_type'] == 'Vendor'].iloc[0]
        alone_vendor = vendor_only_result.iloc[0]

        assert mixed_vendor['total_score'] == alone_vendor['total_score'], (
            f"Vendor score differs in mixed vs isolated scoring: "
            f"{mixed_vendor['total_score']} vs {alone_vendor['total_score']}"
        )

        # Seller scores in mixed vs alone should be identical
        mixed_seller = mixed_result[mixed_result['business_type'] == 'Seller'].iloc[0]
        alone_seller = seller_only_result.iloc[0]

        assert mixed_seller['total_score'] == alone_seller['total_score'], (
            f"Seller score differs in mixed vs isolated scoring: "
            f"{mixed_seller['total_score']} vs {alone_seller['total_score']}"
        )

        # Verify grades match individually too
        for criteria in CRITERIA_NAMES:
            col = f'grade_{criteria}'
            assert mixed_vendor[col] == alone_vendor[col], (
                f"Vendor grade for {criteria} differs mixed vs isolated"
            )
            assert mixed_seller[col] == alone_seller[col], (
                f"Seller grade for {criteria} differs mixed vs isolated"
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
