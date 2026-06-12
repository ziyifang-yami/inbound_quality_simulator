"""
Property-based tests for Weight Configuration Isolation.

**Property 8: Weight Configuration Isolation**
For any modification to the Vendor weight configuration, the Seller weight
configuration SHALL remain unchanged (and vice versa). The two configurations
are stored and updated independently.

**Validates: Requirements 3.5**
"""
import copy

from hypothesis import given, settings
from hypothesis import strategies as st

from config import CRITERIA_NAMES, DEFAULT_WEIGHTS


# Strategy: generate a valid weight dict (10 integer values in [0, 100])
# Not necessarily summing to 100 — we're testing isolation, not validation.
weight_values = st.fixed_dictionaries(
    {name: st.integers(min_value=0, max_value=100) for name in CRITERIA_NAMES}
)


@given(new_vendor_weights=weight_values)
@settings(max_examples=200)
def test_vendor_modification_does_not_affect_seller(new_vendor_weights: dict[str, int]):
    """
    Property 8: Modifying only the 'Vendor' key in a deep-copied weight config
    SHALL NOT change the 'Seller' config.

    **Validates: Requirements 3.5**
    """
    # Start with a deep copy of default weights (matching app.py pattern)
    weights = copy.deepcopy(DEFAULT_WEIGHTS)
    seller_before = copy.deepcopy(weights['Seller'])

    # Modify the Vendor config
    weights['Vendor'] = new_vendor_weights

    # Seller must remain unchanged
    assert weights['Seller'] == seller_before, (
        f"Seller config changed after Vendor modification. "
        f"Expected {seller_before}, got {weights['Seller']}"
    )


@given(new_seller_weights=weight_values)
@settings(max_examples=200)
def test_seller_modification_does_not_affect_vendor(new_seller_weights: dict[str, int]):
    """
    Property 8: Modifying only the 'Seller' key in a deep-copied weight config
    SHALL NOT change the 'Vendor' config.

    **Validates: Requirements 3.5**
    """
    # Start with a deep copy of default weights (matching app.py pattern)
    weights = copy.deepcopy(DEFAULT_WEIGHTS)
    vendor_before = copy.deepcopy(weights['Vendor'])

    # Modify the Seller config
    weights['Seller'] = new_seller_weights

    # Vendor must remain unchanged
    assert weights['Vendor'] == vendor_before, (
        f"Vendor config changed after Seller modification. "
        f"Expected {vendor_before}, got {weights['Vendor']}"
    )


@given(
    criteria=st.sampled_from(CRITERIA_NAMES),
    new_value=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=200)
def test_deep_copy_isolation_vendor_internal_change(criteria: str, new_value: int):
    """
    Property 8 (Deep copy isolation): Changes to individual values within
    the Vendor internal dict SHALL NOT propagate to the Seller dict.

    **Validates: Requirements 3.5**
    """
    # Start with a deep copy (as app.py does)
    weights = copy.deepcopy(DEFAULT_WEIGHTS)
    seller_before = copy.deepcopy(weights['Seller'])

    # Modify a single criteria value within Vendor's internal dict
    weights['Vendor'][criteria] = new_value

    # Seller internal dict must remain unchanged
    assert weights['Seller'] == seller_before, (
        f"Seller config changed after modifying Vendor['{criteria}'] to {new_value}. "
        f"Expected {seller_before}, got {weights['Seller']}"
    )


@given(
    criteria=st.sampled_from(CRITERIA_NAMES),
    new_value=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=200)
def test_deep_copy_isolation_seller_internal_change(criteria: str, new_value: int):
    """
    Property 8 (Deep copy isolation): Changes to individual values within
    the Seller internal dict SHALL NOT propagate to the Vendor dict.

    **Validates: Requirements 3.5**
    """
    # Start with a deep copy (as app.py does)
    weights = copy.deepcopy(DEFAULT_WEIGHTS)
    vendor_before = copy.deepcopy(weights['Vendor'])

    # Modify a single criteria value within Seller's internal dict
    weights['Seller'][criteria] = new_value

    # Vendor internal dict must remain unchanged
    assert weights['Vendor'] == vendor_before, (
        f"Vendor config changed after modifying Seller['{criteria}'] to {new_value}. "
        f"Expected {vendor_before}, got {weights['Vendor']}"
    )
