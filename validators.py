"""
Validation functions for the Inbound Quality Score Simulator.

Provides validation for weight configurations, threshold boundaries,
and tier boundary settings.
"""


def validate_weights(weights: dict[str, int]) -> tuple[bool, str]:
    """
    Returns (is_valid, error_message).
    Valid when sum of all weights == 100 and each weight in [0, 100].
    """
    for name, value in weights.items():
        if value < 0 or value > 100:
            return False, f"Weight '{name}' is {value}, must be between 0 and 100"

    total = sum(weights.values())
    if total != 100:
        diff = total - 100
        if diff > 0:
            return False, f"Weights sum to {total}, exceeds 100 by {diff}"
        else:
            return False, f"Weights sum to {total}, short of 100 by {abs(diff)}"

    return True, ""


def get_remaining_budget(weights: dict[str, int]) -> int:
    """Returns 100 minus the sum of all weight values."""
    return 100 - sum(weights.values())


def validate_thresholds(thresholds: dict[str, float]) -> tuple[bool, str]:
    """
    Validates monotonic ordering: A < B < C for rate-based metrics.
    Returns (is_valid, error_message).
    """
    a = thresholds.get('A')
    b = thresholds.get('B')
    c = thresholds.get('C')

    if a is None or b is None or c is None:
        return False, "Thresholds must contain keys 'A', 'B', and 'C'"

    if not (a < b):
        return False, f"Threshold A ({a}) must be strictly less than B ({b})"
    if not (b < c):
        return False, f"Threshold B ({b}) must be strictly less than C ({c})"

    return True, ""


def validate_tier_boundaries(boundaries: dict[str, float]) -> tuple[bool, str]:
    """
    Validates A > B > C (higher tiers need higher scores).
    Returns (is_valid, error_message).
    """
    a = boundaries.get('A')
    b = boundaries.get('B')
    c = boundaries.get('C')

    if a is None or b is None or c is None:
        return False, "Tier boundaries must contain keys 'A', 'B', and 'C'"

    if not (a > b):
        return False, f"Tier boundary A ({a}) must be strictly greater than B ({b})"
    if not (b > c):
        return False, f"Tier boundary B ({b}) must be strictly greater than C ({c})"

    return True, ""
