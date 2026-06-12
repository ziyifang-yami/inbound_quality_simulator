"""
Scoring engine for the Inbound Quality Score Simulator.

Computes grades per criteria dimension and calculates weighted total scores
for vendor/seller records based on configurable thresholds and weights.
"""

import pandas as pd

from config import CRITERIA_NAMES, DEFAULT_TIER_BOUNDARIES


def compute_grade(rate: float, thresholds: dict) -> int:
    """
    Map a rate to a grade {100, 80, 60, 20} based on threshold boundaries.

    Args:
        rate: The actual rate value (float >= 0). Lower is better.
        thresholds: Dict with keys 'A', 'B', 'C' defining grade boundaries.
                    Must satisfy A < B < C for rate-based metrics.

    Returns:
        Grade as int: 100 if rate <= A, 80 if A < rate <= B,
        60 if B < rate <= C, 20 if rate > C.
    """
    if rate <= thresholds['A']:
        return 100
    elif rate <= thresholds['B']:
        return 80
    elif rate <= thresholds['C']:
        return 60
    else:
        return 20


def classify_tier(score: float, boundaries: dict[str, float]) -> str:
    """
    Assign a tier classification based on total score and boundary thresholds.

    Args:
        score: The total weighted score (typically 0-100).
        boundaries: Dict with keys 'A', 'B', 'C' defining tier cutoffs.
                    Must satisfy A > B > C.

    Returns:
        Tier as str: 'A' if score >= A boundary, 'B' if B <= score < A,
        'C' if C <= score < B, 'D' if score < C.
    """
    if score >= boundaries['A']:
        return 'A'
    elif score >= boundaries['B']:
        return 'B'
    elif score >= boundaries['C']:
        return 'C'
    else:
        return 'D'


def compute_scores(
    df: pd.DataFrame,
    weights: dict[str, dict[str, float]],
    thresholds: dict[str, dict[str, dict]],
    tier_boundaries: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Compute grades and total weighted scores for each vendor/seller record.

    Routes weight and threshold configurations by business_type (Vendor/Seller).
    Adds grade columns (grade_{criteria}), total_score, and tier columns to the DataFrame.

    Args:
        df: Input DataFrame with rate columns ({criteria}_rate for criteria 1-9,
            responsiveness_hours for criteria 10) and a 'business_type' column.
        weights: Nested dict keyed by business type then criteria name.
                 e.g. {'Vendor': {'overage': 15, ...}, 'Seller': {'overage': 10, ...}}
                 Values are percentage points (sum to 100 per business type).
        thresholds: Nested dict keyed by business type, criteria, then grade boundary.
                    e.g. {'Vendor': {'overage': {'A': 0.005, 'B': 0.01, 'C': 0.03}, ...}}
        tier_boundaries: Dict with keys 'A', 'B', 'C' defining tier score cutoffs.
                         Defaults to DEFAULT_TIER_BOUNDARIES if not provided.

    Returns:
        A copy of the input DataFrame with added columns:
        - grade_{criteria}: int (100/80/60/20) for each of 10 criteria
        - total_score: float (0-100) weighted sum
        - tier: str ('A', 'B', 'C', or 'D') based on total_score and tier boundaries
    """
    if tier_boundaries is None:
        tier_boundaries = DEFAULT_TIER_BOUNDARIES

    result = df.copy()

    # Initialize grade columns
    for criteria in CRITERIA_NAMES:
        result[f'grade_{criteria}'] = 0

    result['total_score'] = 0.0

    # Process each row, routing config by business_type
    for idx, row in result.iterrows():
        business_type = row['business_type']
        btype_weights = weights[business_type]
        btype_thresholds = thresholds[business_type]

        total = 0.0
        for criteria in CRITERIA_NAMES:
            # Determine the rate column name
            if criteria == 'responsiveness':
                rate_col = 'responsiveness_hours'
            else:
                rate_col = f'{criteria}_rate'

            rate = row[rate_col]
            grade = compute_grade(rate, btype_thresholds[criteria])
            result.at[idx, f'grade_{criteria}'] = grade

            # Accumulate weighted score (weight is in percentage points)
            weight = btype_weights[criteria]
            total += grade * weight / 100.0

        result.at[idx, 'total_score'] = total

    # Assign tier based on total_score and tier boundaries
    result['tier'] = result['total_score'].apply(
        lambda score: classify_tier(score, tier_boundaries)
    )

    return result
