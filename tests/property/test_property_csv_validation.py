"""
Property-based tests for CSV validation (Property 1: CSV Validation Correctness).

**Validates: Requirements 1.3**

Property 1: CSV Validation Correctness
For any CSV file (represented as a set of column names), the Data_Loader SHALL accept
the file if and only if it contains ALL required columns. Files missing any required
column SHALL be rejected.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypothesis import given, assume, settings
from hypothesis import strategies as st
import pandas as pd

from data_loader import validate_csv_columns
from config import REQUIRED_CSV_COLUMNS


# Strategy: generate a random set of column names (mix of required and extra)
# We draw a subset of required columns plus some random extra columns
extra_column_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    min_size=1,
    max_size=20,
)

# Strategy: generate a subset of required columns (possibly all, possibly none)
required_subset_strategy = st.frozensets(
    st.sampled_from(REQUIRED_CSV_COLUMNS), min_size=0, max_size=len(REQUIRED_CSV_COLUMNS)
)

# Strategy: generate extra non-required column names
extra_columns_strategy = st.lists(
    extra_column_names.filter(lambda x: x not in REQUIRED_CSV_COLUMNS),
    min_size=0,
    max_size=10,
)


class TestCSVValidationCorrectnessProperty:
    """
    Property 1: CSV Validation Correctness

    **Validates: Requirements 1.3**
    """

    @given(
        included_required=required_subset_strategy,
        extras=extra_columns_strategy,
    )
    @settings(max_examples=200)
    def test_validation_accepts_iff_all_required_present(
        self, included_required: frozenset, extras: list
    ):
        """
        For any set of column names, validate_csv_columns returns (True, [])
        if and only if ALL required columns are present. Otherwise returns
        (False, missing_list) with the correct missing columns.

        This is the biconditional property: valid iff all required columns present.

        **Validates: Requirements 1.3**
        """
        columns = list(included_required) + extras
        df = pd.DataFrame(columns=columns)

        is_valid, missing = validate_csv_columns(df)

        all_required_present = set(REQUIRED_CSV_COLUMNS).issubset(set(columns))

        if all_required_present:
            assert is_valid is True, (
                f"Expected valid=True when all required columns present, "
                f"but got False. Missing reported: {missing}"
            )
            assert missing == [], (
                f"Expected empty missing list when valid, got: {missing}"
            )
        else:
            assert is_valid is False, (
                f"Expected valid=False when required columns missing, "
                f"but got True. Columns: {columns}"
            )
            assert len(missing) > 0, (
                "Expected non-empty missing list when invalid"
            )
            # Verify the missing list is exactly the set difference
            expected_missing = set(REQUIRED_CSV_COLUMNS) - set(columns)
            assert set(missing) == expected_missing, (
                f"Missing columns mismatch. Expected: {expected_missing}, "
                f"Got: {set(missing)}"
            )

    @given(extras=extra_columns_strategy)
    @settings(max_examples=100)
    def test_all_required_columns_present_always_valid(self, extras: list):
        """
        When ALL required columns are present (plus any extra columns),
        validation always returns (True, []).

        **Validates: Requirements 1.3**
        """
        columns = list(REQUIRED_CSV_COLUMNS) + extras
        df = pd.DataFrame(columns=columns)

        is_valid, missing = validate_csv_columns(df)

        assert is_valid is True, (
            f"All required columns present but validation failed. "
            f"Missing reported: {missing}"
        )
        assert missing == [], (
            f"Expected empty missing list when all required present, got: {missing}"
        )

    @given(
        columns_to_remove=st.frozensets(
            st.sampled_from(REQUIRED_CSV_COLUMNS), min_size=1
        ),
        extras=extra_columns_strategy,
    )
    @settings(max_examples=200)
    def test_missing_required_columns_always_invalid(
        self, columns_to_remove: frozenset, extras: list
    ):
        """
        When any required column is missing, validation returns (False, list_with_missing)
        and the missing list contains exactly the removed columns.

        **Validates: Requirements 1.3**
        """
        remaining_required = [
            col for col in REQUIRED_CSV_COLUMNS if col not in columns_to_remove
        ]
        columns = remaining_required + extras
        df = pd.DataFrame(columns=columns)

        is_valid, missing = validate_csv_columns(df)

        assert is_valid is False, (
            f"Expected invalid when columns {columns_to_remove} removed, "
            f"but got valid=True"
        )
        assert set(missing) == set(columns_to_remove), (
            f"Missing columns mismatch. Removed: {columns_to_remove}, "
            f"Reported missing: {missing}"
        )
