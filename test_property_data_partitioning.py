"""
Property-based tests for data partitioning completeness (Property 2).

**Validates: Requirements 1.4**

Property 2: Data Partitioning Completeness
For any loaded DataFrame containing records with mixed warehouse_number and
business_type values, partitioning by warehouse and business_type SHALL produce
subsets whose union equals the original dataset (no records lost) and whose
intersection is empty (no records duplicated across partitions).

The partition logic uses simple pandas filtering:
- By warehouse: df[df['warehouse_number'] == 'LA'] and df[df['warehouse_number'] == 'NJ']
- By business_type: df[df['business_type'] == 'Vendor'] and df[df['business_type'] == 'Seller']
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from config import CRITERIA_NAMES


# --- Strategies ---


@st.composite
def random_dataframe(draw):
    """
    Generate a DataFrame with random rows containing mixed warehouse_number
    and business_type values, along with random numeric column values.
    """
    n_rows = draw(st.integers(min_value=1, max_value=50))

    rows = []
    for i in range(n_rows):
        warehouse = draw(st.sampled_from(['LA', 'NJ']))
        business_type = draw(st.sampled_from(['Vendor', 'Seller']))
        team = draw(st.sampled_from(['Food', 'Non-food', 'TTL']))
        qty_received = draw(st.integers(min_value=1, max_value=10000))

        row = {
            'warehouse_number': warehouse,
            'vendor_id': i + 1,
            'vendor_name': f'Test Vendor {i + 1}',
            'business_type': business_type,
            'team': team,
            'qty_received': qty_received,
        }

        # Generate random rate values for all criteria
        for criteria in CRITERIA_NAMES:
            if criteria == 'responsiveness':
                row['responsiveness_hours'] = draw(
                    st.floats(min_value=0.0, max_value=168.0,
                              allow_nan=False, allow_infinity=False)
                )
            else:
                row[f'{criteria}_rate'] = draw(
                    st.floats(min_value=0.0, max_value=1.0,
                              allow_nan=False, allow_infinity=False)
                )

        rows.append(row)

    return pd.DataFrame(rows)


# --- Property Tests ---


class TestDataPartitioningCompleteness:
    """
    **Validates: Requirements 1.4**

    Property 2: Data Partitioning Completeness
    Generate DataFrames with mixed warehouse/business_type; partitioning produces
    non-overlapping subsets whose union equals original.
    """

    @given(df=random_dataframe())
    @settings(max_examples=200, deadline=None)
    def test_warehouse_partition_union_equals_original(self, df):
        """
        Partitioning by warehouse → union of LA + NJ subsets == original DataFrame.
        No records are lost during partitioning.
        """
        la_df = df[df['warehouse_number'] == 'LA']
        nj_df = df[df['warehouse_number'] == 'NJ']

        # Union of partitions should have the same total number of rows
        assert len(la_df) + len(nj_df) == len(df), (
            f"Row count mismatch: LA({len(la_df)}) + NJ({len(nj_df)}) != "
            f"original({len(df)})"
        )

        # Reconstruct the union and verify equality with original
        union_df = pd.concat([la_df, nj_df], ignore_index=False).sort_index()
        pd.testing.assert_frame_equal(
            union_df.reset_index(drop=True),
            df.reset_index(drop=True),
            check_dtype=False,
        )

    @given(df=random_dataframe())
    @settings(max_examples=200, deadline=None)
    def test_warehouse_partition_no_overlap(self, df):
        """
        Partitioning by warehouse → LA and NJ subsets have empty intersection.
        No records appear in both partitions.
        """
        la_df = df[df['warehouse_number'] == 'LA']
        nj_df = df[df['warehouse_number'] == 'NJ']

        # Intersection should be empty — index sets should not overlap
        la_indices = set(la_df.index)
        nj_indices = set(nj_df.index)
        overlap = la_indices & nj_indices

        assert len(overlap) == 0, (
            f"Warehouse partitions overlap at indices: {overlap}"
        )

        # Additionally verify: no row can have warehouse != 'LA' in la_df
        if len(la_df) > 0:
            assert (la_df['warehouse_number'] == 'LA').all(), (
                "LA partition contains non-LA records"
            )
        if len(nj_df) > 0:
            assert (nj_df['warehouse_number'] == 'NJ').all(), (
                "NJ partition contains non-NJ records"
            )

    @given(df=random_dataframe())
    @settings(max_examples=200, deadline=None)
    def test_business_type_partition_union_equals_original(self, df):
        """
        Partitioning by business_type → union of Vendor + Seller subsets == original.
        No records are lost during partitioning.
        """
        vendor_df = df[df['business_type'] == 'Vendor']
        seller_df = df[df['business_type'] == 'Seller']

        # Union of partitions should have the same total number of rows
        assert len(vendor_df) + len(seller_df) == len(df), (
            f"Row count mismatch: Vendor({len(vendor_df)}) + Seller({len(seller_df)}) "
            f"!= original({len(df)})"
        )

        # Reconstruct the union and verify equality with original
        union_df = pd.concat([vendor_df, seller_df], ignore_index=False).sort_index()
        pd.testing.assert_frame_equal(
            union_df.reset_index(drop=True),
            df.reset_index(drop=True),
            check_dtype=False,
        )

    @given(df=random_dataframe())
    @settings(max_examples=200, deadline=None)
    def test_business_type_partition_no_overlap(self, df):
        """
        Partitioning by business_type → Vendor and Seller subsets have empty intersection.
        No records appear in both partitions.
        """
        vendor_df = df[df['business_type'] == 'Vendor']
        seller_df = df[df['business_type'] == 'Seller']

        # Intersection should be empty — index sets should not overlap
        vendor_indices = set(vendor_df.index)
        seller_indices = set(seller_df.index)
        overlap = vendor_indices & seller_indices

        assert len(overlap) == 0, (
            f"Business type partitions overlap at indices: {overlap}"
        )

        # Additionally verify: no row can have business_type != 'Vendor' in vendor_df
        if len(vendor_df) > 0:
            assert (vendor_df['business_type'] == 'Vendor').all(), (
                "Vendor partition contains non-Vendor records"
            )
        if len(seller_df) > 0:
            assert (seller_df['business_type'] == 'Seller').all(), (
                "Seller partition contains non-Seller records"
            )

    @given(df=random_dataframe())
    @settings(max_examples=200, deadline=None)
    def test_combined_partition_four_subsets_union_equals_original(self, df):
        """
        Combined partition (warehouse × business_type) → 4 non-overlapping subsets
        whose union equals the original DataFrame.
        """
        la_vendor = df[(df['warehouse_number'] == 'LA') & (df['business_type'] == 'Vendor')]
        la_seller = df[(df['warehouse_number'] == 'LA') & (df['business_type'] == 'Seller')]
        nj_vendor = df[(df['warehouse_number'] == 'NJ') & (df['business_type'] == 'Vendor')]
        nj_seller = df[(df['warehouse_number'] == 'NJ') & (df['business_type'] == 'Seller')]

        # Total count across all 4 partitions should equal original
        total = len(la_vendor) + len(la_seller) + len(nj_vendor) + len(nj_seller)
        assert total == len(df), (
            f"Combined partition row count mismatch: "
            f"LA_Vendor({len(la_vendor)}) + LA_Seller({len(la_seller)}) + "
            f"NJ_Vendor({len(nj_vendor)}) + NJ_Seller({len(nj_seller)}) = {total} "
            f"!= original({len(df)})"
        )

        # Reconstruct the union and verify equality with original
        union_df = pd.concat(
            [la_vendor, la_seller, nj_vendor, nj_seller],
            ignore_index=False
        ).sort_index()
        pd.testing.assert_frame_equal(
            union_df.reset_index(drop=True),
            df.reset_index(drop=True),
            check_dtype=False,
        )

    @given(df=random_dataframe())
    @settings(max_examples=200, deadline=None)
    def test_combined_partition_no_overlap_between_any_pair(self, df):
        """
        Combined partition (warehouse × business_type) → all 4 subsets are mutually
        non-overlapping (no index appears in more than one partition).
        """
        la_vendor = df[(df['warehouse_number'] == 'LA') & (df['business_type'] == 'Vendor')]
        la_seller = df[(df['warehouse_number'] == 'LA') & (df['business_type'] == 'Seller')]
        nj_vendor = df[(df['warehouse_number'] == 'NJ') & (df['business_type'] == 'Vendor')]
        nj_seller = df[(df['warehouse_number'] == 'NJ') & (df['business_type'] == 'Seller')]

        index_sets = [
            ('LA_Vendor', set(la_vendor.index)),
            ('LA_Seller', set(la_seller.index)),
            ('NJ_Vendor', set(nj_vendor.index)),
            ('NJ_Seller', set(nj_seller.index)),
        ]

        # Check all pairs for non-overlap
        for i in range(len(index_sets)):
            for j in range(i + 1, len(index_sets)):
                name_i, set_i = index_sets[i]
                name_j, set_j = index_sets[j]
                overlap = set_i & set_j
                assert len(overlap) == 0, (
                    f"Overlap between {name_i} and {name_j} at indices: {overlap}"
                )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
