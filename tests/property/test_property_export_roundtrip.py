"""
Property-based tests for export round-trip (Property 14: Export Round-Trip).

**Validates: Requirements 9.1, 9.3**

Property 14: Export Round-Trip
For any scored DataFrame and parameter state (weights, thresholds, boundaries),
exporting to CSV and re-parsing SHALL produce a DataFrame equivalent to the
original scored data, and the parsed metadata section SHALL contain the exact
parameter values used for the export.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import io
import json

import pandas as pd
import numpy as np
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from exporter import export_csv
from config import CRITERIA_NAMES


# --- Strategies ---

# Strategy: generate tier boundaries (A > B > C, all in [1, 100])
@st.composite
def tier_boundaries_st(draw):
    """Generate valid tier boundaries where A > B > C."""
    # Draw three distinct values and sort descending
    vals = draw(st.lists(
        st.integers(min_value=1, max_value=100),
        min_size=3, max_size=3,
    ))
    vals_sorted = sorted(set(vals), reverse=True)
    assume(len(vals_sorted) >= 3)
    return {"A": vals_sorted[0], "B": vals_sorted[1], "C": vals_sorted[2]}


tier_boundaries_strategy = tier_boundaries_st()


# Strategy: generate a valid weight dict (10 criteria, each [0,100], sum == 100)
@st.composite
def weights_dict_strategy(draw):
    """Generate a dict of 10 criteria weights summing to exactly 100."""
    # Use a stick-breaking approach: distribute 100 among 10 buckets
    remaining = 100
    values = []
    for i in range(9):
        val = draw(st.integers(min_value=0, max_value=remaining))
        values.append(val)
        remaining -= val
    values.append(remaining)  # Last value takes the remainder
    return dict(zip(CRITERIA_NAMES, values))


weights_strategy = st.fixed_dictionaries({
    "Vendor": weights_dict_strategy(),
    "Seller": weights_dict_strategy(),
})

# Strategy: generate threshold values for one criteria (A < B < C, positive)
@st.composite
def single_threshold_st(draw):
    """Generate a valid threshold with A < B < C."""
    a = draw(st.floats(min_value=0.001, max_value=0.1, allow_nan=False, allow_infinity=False))
    b = draw(st.floats(min_value=0.001, max_value=0.3, allow_nan=False, allow_infinity=False))
    c = draw(st.floats(min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False))
    # Sort to guarantee A < B < C
    vals = sorted([a, b, c])
    assume(vals[0] < vals[1] < vals[2])
    return {"A": round(vals[0], 4), "B": round(vals[1], 4), "C": round(vals[2], 4)}


single_threshold_strategy = single_threshold_st()


def _generate_thresholds_for_type():
    """Generate threshold dict for all 10 criteria."""
    return st.fixed_dictionaries({
        name: single_threshold_st() for name in CRITERIA_NAMES
    })


thresholds_strategy = st.fixed_dictionaries({
    "Vendor": _generate_thresholds_for_type(),
    "Seller": _generate_thresholds_for_type(),
})

# Strategy: generate a scored DataFrame with realistic columns
# Includes base columns + grade columns + total_score + tier
RATE_COLUMNS = [
    "overage_rate", "damage_rate", "upc_error_rate", "exp_error_rate",
    "po_error_rate", "no_data_rate", "spec_image_error_rate",
    "packaging_error_rate", "poor_quality_rate", "responsiveness_hours",
]
GRADE_COLUMNS = [f"grade_{c}" for c in CRITERIA_NAMES]


@st.composite
def scored_dataframe_strategy(draw, min_rows=1, max_rows=10):
    """Generate a scored DataFrame with random data."""
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))

    data = {
        "warehouse_number": draw(
            st.lists(
                st.sampled_from(["001", "002"]),
                min_size=n_rows, max_size=n_rows,
            )
        ),
        "vendor_id": draw(
            st.lists(
                st.integers(min_value=1000, max_value=99999),
                min_size=n_rows, max_size=n_rows,
            )
        ),
        "vendor_name": draw(
            st.lists(
                st.text(
                    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_- "),
                    min_size=1, max_size=20,
                ),
                min_size=n_rows, max_size=n_rows,
            )
        ),
        "business_type": draw(
            st.lists(
                st.sampled_from(["Vendor", "Seller"]),
                min_size=n_rows, max_size=n_rows,
            )
        ),
        "qty_received": draw(
            st.lists(
                st.integers(min_value=1, max_value=100000),
                min_size=n_rows, max_size=n_rows,
            )
        ),
    }

    # Add rate columns (floats between 0 and 1)
    for col in RATE_COLUMNS[:-1]:  # all except responsiveness_hours
        data[col] = draw(
            st.lists(
                st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                min_size=n_rows, max_size=n_rows,
            )
        )
    # responsiveness_hours (float, 0 to 200)
    data["responsiveness_hours"] = draw(
        st.lists(
            st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False),
            min_size=n_rows, max_size=n_rows,
        )
    )

    # Add grade columns (each is 100, 80, 60, or 20)
    for col in GRADE_COLUMNS:
        data[col] = draw(
            st.lists(
                st.sampled_from([100, 80, 60, 20]),
                min_size=n_rows, max_size=n_rows,
            )
        )

    # Total score (float between 20 and 100)
    data["total_score"] = draw(
        st.lists(
            st.floats(min_value=20.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=n_rows, max_size=n_rows,
        )
    )

    # Tier assignment
    data["tier"] = draw(
        st.lists(
            st.sampled_from(["A", "B", "C", "D"]),
            min_size=n_rows, max_size=n_rows,
        )
    )

    return pd.DataFrame(data)


def parse_exported_csv(csv_bytes: bytes) -> tuple[pd.DataFrame, dict]:
    """
    Parse exported CSV bytes into (DataFrame, metadata_dict).

    Metadata is extracted from lines starting with '#'.
    Data rows are the non-comment lines parsed as CSV.
    """
    text = csv_bytes.decode("utf-8")
    lines = text.split("\n")

    metadata_lines = []
    data_lines = []
    for line in lines:
        if line.startswith("#"):
            metadata_lines.append(line)
        else:
            data_lines.append(line)

    # Parse metadata
    metadata = {}
    for line in metadata_lines:
        content = line.lstrip("# ").strip()
        if "Tier Boundaries:" in content:
            json_str = content.split("Tier Boundaries:", 1)[1].strip()
            metadata["tier_boundaries"] = json.loads(json_str)
        elif "Weights:" in content:
            json_str = content.split("Weights:", 1)[1].strip()
            metadata["weights"] = json.loads(json_str)
        elif "Thresholds:" in content:
            json_str = content.split("Thresholds:", 1)[1].strip()
            metadata["thresholds"] = json.loads(json_str)

    # Parse data as CSV, keeping warehouse_number and vendor_id as strings
    # to preserve leading zeros (e.g., '001' not parsed as int 1)
    data_text = "\n".join(data_lines)
    if data_text.strip():
        df = pd.read_csv(
            io.StringIO(data_text),
            dtype={"warehouse_number": str, "vendor_id": str},
        )
    else:
        df = pd.DataFrame()

    return df, metadata


class TestExportRoundTripProperty:
    """
    Property 14: Export Round-Trip

    **Validates: Requirements 9.1, 9.3**
    """

    @given(
        df=scored_dataframe_strategy(),
        weights=weights_strategy,
        thresholds=thresholds_strategy,
        tier_boundaries=tier_boundaries_strategy,
    )
    @settings(max_examples=50, deadline=None)
    def test_data_rows_preserved_after_round_trip(
        self, df, weights, thresholds, tier_boundaries
    ):
        """
        Export to CSV bytes, then re-parse (skip comment lines), verify data rows
        match original DataFrame in number of rows and column names.

        **Validates: Requirements 9.1**
        """
        csv_bytes = export_csv(df, weights, thresholds, tier_boundaries)
        parsed_df, _ = parse_exported_csv(csv_bytes)

        # Same number of rows
        assert len(parsed_df) == len(df), (
            f"Row count mismatch: original={len(df)}, parsed={len(parsed_df)}"
        )

        # Same columns
        assert set(parsed_df.columns) == set(df.columns), (
            f"Column mismatch. Original: {set(df.columns)}, "
            f"Parsed: {set(parsed_df.columns)}"
        )

    @given(
        df=scored_dataframe_strategy(),
        weights=weights_strategy,
        thresholds=thresholds_strategy,
        tier_boundaries=tier_boundaries_strategy,
    )
    @settings(max_examples=50, deadline=None)
    def test_metadata_contains_correct_parameters(
        self, df, weights, thresholds, tier_boundaries
    ):
        """
        The metadata section contains the correct tier_boundaries, weights,
        and thresholds as JSON.

        **Validates: Requirements 9.3**
        """
        csv_bytes = export_csv(df, weights, thresholds, tier_boundaries)
        _, metadata = parse_exported_csv(csv_bytes)

        # Verify tier boundaries match
        assert metadata.get("tier_boundaries") == tier_boundaries, (
            f"Tier boundaries mismatch. Expected: {tier_boundaries}, "
            f"Got: {metadata.get('tier_boundaries')}"
        )

        # Verify weights match
        assert metadata.get("weights") == weights, (
            f"Weights mismatch. Expected: {weights}, "
            f"Got: {metadata.get('weights')}"
        )

        # Verify thresholds match
        assert metadata.get("thresholds") == thresholds, (
            f"Thresholds mismatch. Expected: {thresholds}, "
            f"Got: {metadata.get('thresholds')}"
        )

    @given(
        df=scored_dataframe_strategy(),
        weights=weights_strategy,
        thresholds=thresholds_strategy,
        tier_boundaries=tier_boundaries_strategy,
    )
    @settings(max_examples=50, deadline=None)
    def test_column_values_preserved_after_round_trip(
        self, df, weights, thresholds, tier_boundaries
    ):
        """
        Round-trip preserves all column values (accounting for float precision).
        String columns match exactly; numeric columns match within tolerance.

        **Validates: Requirements 9.1, 9.3**
        """
        csv_bytes = export_csv(df, weights, thresholds, tier_boundaries)
        parsed_df, _ = parse_exported_csv(csv_bytes)

        # Compare string columns exactly
        string_cols = ["warehouse_number", "vendor_id", "vendor_name", "business_type", "tier"]
        for col in string_cols:
            if col in df.columns and col in parsed_df.columns:
                original_vals = df[col].astype(str).tolist()
                parsed_vals = parsed_df[col].astype(str).tolist()
                assert original_vals == parsed_vals, (
                    f"String column '{col}' mismatch at some row. "
                    f"Original: {original_vals}, Parsed: {parsed_vals}"
                )

        # Compare integer columns
        int_cols = ["qty_received"] + GRADE_COLUMNS
        for col in int_cols:
            if col in df.columns and col in parsed_df.columns:
                original_vals = df[col].tolist()
                parsed_vals = parsed_df[col].tolist()
                for i, (orig, pars) in enumerate(zip(original_vals, parsed_vals)):
                    assert int(orig) == int(pars), (
                        f"Integer column '{col}' mismatch at row {i}: "
                        f"original={orig}, parsed={pars}"
                    )

        # Compare float columns with tolerance
        float_cols = RATE_COLUMNS + ["total_score"]
        for col in float_cols:
            if col in df.columns and col in parsed_df.columns:
                original_vals = df[col].values
                parsed_vals = parsed_df[col].values
                np.testing.assert_allclose(
                    parsed_vals, original_vals, rtol=1e-5, atol=1e-10,
                    err_msg=f"Float column '{col}' values differ beyond tolerance",
                )
