"""
Impact Analyzer for the Inbound Quality Score Simulator.

Compares tier assignments between a baseline scoring (default parameters) and
a current scoring (user-adjusted parameters) to identify tier movements,
upgrades, downgrades, and affected vendors/sellers.
"""

import pandas as pd


# Tier ordering: A is best (rank 0), D is worst (rank 3)
TIER_RANK = {'A': 0, 'B': 1, 'C': 2, 'D': 3}


def analyze_impact(
    baseline_df: pd.DataFrame,
    current_df: pd.DataFrame,
) -> dict:
    """
    Compare tier assignments between baseline and current scored DataFrames.

    Identifies all vendors/sellers whose tier changed, classifies each change
    as an upgrade or downgrade, and computes transition counts.

    Also modifies current_df in-place to add:
    - 'baseline_tier': str (tier from baseline)
    - 'tier_changed': bool (True if tier differs from baseline)
    - 'tier_direction': str ('upgrade', 'downgrade', or 'same')

    Args:
        baseline_df: Scored DataFrame with 'tier' and 'vendor_id' columns
                     (produced by compute_scores with default parameters).
        current_df: Scored DataFrame with 'tier' and 'vendor_id' columns
                    (produced by compute_scores with current parameters).

    Returns:
        Dict with keys:
        - 'changed_count': int — total number of vendors/sellers whose tier changed
        - 'upgrades': int — count of vendors who moved to a higher (better) tier
        - 'downgrades': int — count of vendors who moved to a lower (worse) tier
        - 'transitions': dict[str, int] — counts per transition, e.g. {'B→A': 5, 'C→D': 3}
        - 'changed_vendors': list[int] — vendor_ids of all vendors whose tier changed
    """
    # Add baseline_tier column to current_df by positional alignment.
    # Both DataFrames originate from the same raw data with the same row order,
    # so we align by index. This avoids issues with duplicate vendor_ids
    # (e.g., same vendor appearing in multiple warehouses).
    current_df['baseline_tier'] = baseline_df['tier'].values

    # Determine whether tier changed
    current_df['tier_changed'] = current_df['tier'] != current_df['baseline_tier']

    # Determine direction of change
    current_df['tier_direction'] = current_df.apply(
        lambda row: _classify_direction(row['baseline_tier'], row['tier']),
        axis=1,
    )

    # Filter to only changed records
    changed_mask = current_df['tier_changed']
    changed_df = current_df[changed_mask]

    # Count upgrades and downgrades
    upgrades = int((changed_df['tier_direction'] == 'upgrade').sum())
    downgrades = int((changed_df['tier_direction'] == 'downgrade').sum())

    # Build transitions dict (e.g. {'B→A': 5, 'C→D': 3})
    transitions: dict[str, int] = {}
    if not changed_df.empty:
        transition_series = (
            changed_df['baseline_tier'] + '→' + changed_df['tier']
        )
        transitions = transition_series.value_counts().to_dict()
        # Ensure values are plain int (not numpy int64)
        transitions = {k: int(v) for k, v in transitions.items()}

    # List of changed vendor_ids
    changed_vendors = changed_df['vendor_id'].tolist()

    return {
        'changed_count': int(changed_mask.sum()),
        'upgrades': upgrades,
        'downgrades': downgrades,
        'transitions': transitions,
        'changed_vendors': changed_vendors,
    }


def _classify_direction(baseline_tier: str, current_tier: str) -> str:
    """
    Classify the direction of a tier change.

    Tier order: A > B > C > D (A is best, D is worst).
    Lower rank number = better tier.

    Args:
        baseline_tier: The tier under default parameters.
        current_tier: The tier under current parameters.

    Returns:
        'upgrade' if current tier is better (lower rank),
        'downgrade' if current tier is worse (higher rank),
        'same' if tiers are equal.
    """
    baseline_rank = TIER_RANK.get(baseline_tier, 3)
    current_rank = TIER_RANK.get(current_tier, 3)

    if current_rank < baseline_rank:
        return 'upgrade'
    elif current_rank > baseline_rank:
        return 'downgrade'
    else:
        return 'same'
