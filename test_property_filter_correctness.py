"""
Property-based tests for filter correctness (Property 13).

**Validates: Requirements 8.4**

Property 13: Filter Correctness
For any dataset and any combination of filter values (warehouse, business_type, team),
the filtered result SHALL contain exactly those records matching ALL active filter
criteria, with no matching records excluded and no non-matching records included.

The filter logic replicates _apply_filters from app.py:
- warehouse filter: df[df['warehouse_number'] == value] (or all if "All")
- business_type filter: df[df['business_type'] == value] (or all if "All")
- team filter: df[df['team'] == value] (or all if "All")
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import numpy as np
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from config import CRITERIA_NAMES


# --- Filter function under test (replicated from app.py _apply_filters) ---


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    Apply filter criteria to the DataFrame.
    Replicates the _apply_filters logic from app.py without Streamlit dependency.
    """
    filtered = df.copy()
    if filters["warehouse"] != "All":
        filtered = filtered[filtered["warehouse_number"] == filters["warehouse"]]
    if filters["business_type"] != "All":
        filtered = filtered[filtered["business_type"] == filters["business_type"]]
    if filters["team"] != "All":
        filtered = filtered[filtered["team"] == filters["team"]]
    return filtered


# --- Strategies ---

WAREHOUSE_VALUES = ['LA', 'NJ']
BUSINESS_TYPE_VALUES = ['Vendor', 'Seller']
TEAM_VALUES = ['Food', 'Non-food', 'TTL']

WAREHOUSE_FILTER_VALUES = ['All'] + WAREHOUSE_VALUES
BUSINESS_TYPE_FILTER_VALUES = ['All'] + BUSINESS_TYPE_VALUES
TEAM_FILTER_VALUES = ['All'] + TEAM_VALUES


@st.composite
def random_dataframe(draw):
    """
    Generate a DataFrame with random rows containing mixed warehouse_number,
    business_type, and team values.
    """
    n_rows = draw(st.integers(min_value=1, max_value=50))

    rows = []
    for i in range(n_rows):
        warehouse = draw(st.sampled_from(WAREHOUSE_VALUES))
        business_type = draw(st.sampled_from(BUSINESS_TYPE_VALUES))
        team = draw(st.sampled_from(TEAM_VALUES))
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


@st.composite
def random_filters(draw):
    """Generate a random combination of filter values."""
    return {
        'warehouse': draw(st.sampled_from(WAREHOUSE_FILTER_VALUES)),
        'business_type': draw(st.sampled_from(BUSINESS_TYPE_FILTER_VALUES)),
        'team': draw(st.sampled_from(TEAM_FILTER_VALUES)),
    }


@st.composite
def dataframe_and_filters(draw):
    """Generate a DataFrame paired with a random filter combination."""
    df = draw(random_dataframe())
    filters = draw(random_filters())
    return df, filters


# --- Property Tests ---


class TestFilterCorrectness:
    """
    **Validates: Requirements 8.4**

    Property 13: Filter Correctness
    Generate datasets × filter combinations; filtered result contains exactly
    matching records, no omissions or extras.
    """

    @given(data=dataframe_and_filters())
    @settings(max_examples=200, deadline=None)
    def test_filtered_result_contains_only_matching_records(self, data):
        """
        Filtered result contains ONLY records matching ALL active filter criteria.
        No non-matching records are included.
        """
        df, filters = data
        filtered = apply_filters(df, filters)

        # Every record in the filtered result must satisfy all active filters
        for _, row in filtered.iterrows():
            if filters["warehouse"] != "All":
                assert row["warehouse_number"] == filters["warehouse"], (
                    f"Non-matching warehouse record found: "
                    f"expected '{filters['warehouse']}', got '{row['warehouse_number']}'"
                )
            if filters["business_type"] != "All":
                assert row["business_type"] == filters["business_type"], (
                    f"Non-matching business_type record found: "
                    f"expected '{filters['business_type']}', got '{row['business_type']}'"
                )
            if filters["team"] != "All":
                assert row["team"] == filters["team"], (
                    f"Non-matching team record found: "
                    f"expected '{filters['team']}', got '{row['team']}'"
                )

    @given(data=dataframe_and_filters())
    @settings(max_examples=200, deadline=None)
    def test_no_matching_records_omitted(self, data):
        """
        Every record matching the filter criteria IS in the filtered result (no omissions).
        """
        df, filters = data
        filtered = apply_filters(df, filters)

        # Build the expected mask manually
        mask = pd.Series([True] * len(df), index=df.index)
        if filters["warehouse"] != "All":
            mask = mask & (df["warehouse_number"] == filters["warehouse"])
        if filters["business_type"] != "All":
            mask = mask & (df["business_type"] == filters["business_type"])
        if filters["team"] != "All":
            mask = mask & (df["team"] == filters["team"])

        expected_indices = set(df[mask].index)
        actual_indices = set(filtered.index)

        # Every matching record in the original must appear in the filtered result
        missing = expected_indices - actual_indices
        assert len(missing) == 0, (
            f"Matching records omitted from filtered result at indices: {missing}"
        )

    @given(data=dataframe_and_filters())
    @settings(max_examples=200, deadline=None)
    def test_filtered_count_equals_matching_count(self, data):
        """
        The count of filtered records equals the count of matching records
        in the original dataset.
        """
        df, filters = data
        filtered = apply_filters(df, filters)

        # Count matching records independently
        mask = pd.Series([True] * len(df), index=df.index)
        if filters["warehouse"] != "All":
            mask = mask & (df["warehouse_number"] == filters["warehouse"])
        if filters["business_type"] != "All":
            mask = mask & (df["business_type"] == filters["business_type"])
        if filters["team"] != "All":
            mask = mask & (df["team"] == filters["team"])

        expected_count = mask.sum()
        actual_count = len(filtered)

        assert actual_count == expected_count, (
            f"Filtered count ({actual_count}) != expected matching count "
            f"({expected_count}) for filters {filters}"
        )

    @given(df=random_dataframe())
    @settings(max_examples=200, deadline=None)
    def test_all_filters_returns_full_dataset(self, df):
        """
        Filter with "All" on all dimensions returns the full dataset.
        """
        filters = {'warehouse': 'All', 'business_type': 'All', 'team': 'All'}
        filtered = apply_filters(df, filters)

        assert len(filtered) == len(df), (
            f"All-filter should return full dataset: "
            f"got {len(filtered)} rows, expected {len(df)}"
        )

        # Verify exact equality of content
        pd.testing.assert_frame_equal(
            filtered.reset_index(drop=True),
            df.reset_index(drop=True),
            check_dtype=False,
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
