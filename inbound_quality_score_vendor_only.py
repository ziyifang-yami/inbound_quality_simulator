"""
Inbound Quality Score Calculator — VENDOR ONLY
================================================
This is the Vendor-only version. Seller data is excluded.

Connects to MySQL DB, loads 180 days of Vendor inbound quality data,
computes error rates, grades each criteria dimension, calculates
weighted total scores, and assigns A/B/C/D tiers.

NOTE: Responsiveness criteria has 0% weight for Vendors, so it does
not affect the final score.

Output: CSV with Vendor scores only.

Data Sources:
  - MySQL (yamibuy_wh, yamibuy_po, yamibuy_im)

Scoring Reference:
  - Google Sheet: https://docs.google.com/spreadsheets/d/1HNEzs65WF03vaEY1flrb9vOHJJHBID30QSo_-ybU6sE/
  - Tab: "Criteria Details" (weights & thresholds)

Author: Ops Analytics Team
Last Updated: 2026-07-14
"""

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# =============================================================================
# 1. CONFIGURATION — Weights, Thresholds, Tier Boundaries
# =============================================================================
# Source: Google Sheet "Criteria Details" tab, Rows 3-12 (criteria), Row 31-32 (weights)

CRITERIA_NAMES = [
    'damage', 'exp_error', 'overage', 'spec_image_error', 'no_data',
    'upc_error', 'packaging_error', 'po_error', 'responsiveness', 'poor_quality'
]

# Weights per business type (must sum to 1.0)
WEIGHTS = {
    'Vendor': {
        'damage': 0.15,
        'exp_error': 0.15,
        'overage': 0.15,
        'spec_image_error': 0.05,
        'no_data': 0.10,
        'upc_error': 0.10,
        'packaging_error': 0.10,
        'po_error': 0.05,
        'responsiveness': 0.00,   # 0% weight for Vendor
        'poor_quality': 0.15,
    },
}

# Grade thresholds: rate <= A → 100, A < rate <= B → 80, B < rate <= C → 60, > C → 20
THRESHOLDS = {
    'Vendor': {
        'damage':           {'A': 0.0001, 'B': 0.0005, 'C': 0.0025},
        'exp_error':        {'A': 0.0001, 'B': 0.01,   'C': 0.05},
        'overage':          {'A': 0.0001, 'B': 0.005,  'C': 0.02},
        'spec_image_error': {'A': 0.0001, 'B': 0.03,   'C': 0.05},
        'no_data':          {'A': 0.0001, 'B': 0.005,  'C': 0.05},
        'upc_error':        {'A': 0.0001, 'B': 0.005,  'C': 0.05},
        'packaging_error':  {'A': 0.0001, 'B': 0.005,  'C': 0.01},
        'po_error':         {'A': 0.0001, 'B': 0.01,   'C': 0.05},
        'responsiveness':   {'A': 1.5,    'B': 3,      'C': 7},
        'poor_quality':     {'A': 0.0001, 'B': 0.0005, 'C': 0.002},
    },
}

# Tier classification boundaries
TIER_BOUNDARIES = {'A': 95, 'B': 80, 'C': 65}  # C changed from 60 to 65


# =============================================================================
# 2. DATABASE CONNECTION
# =============================================================================

def get_engine():
    """Create SQLAlchemy engine from .env credentials."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        env_path = Path(
            r"C:\Users\ziyi.fang\OneDrive - YAMIBUY.COM\Documents\Ziyi\Project\config\.env"
        )
    load_dotenv(dotenv_path=env_path, override=True)

    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASS")
    host = os.getenv("MYSQL_HOST")
    if not all([user, password, host]):
        raise EnvironmentError(
            "Missing DB credentials. Set MYSQL_USER, MYSQL_PASS, MYSQL_HOST in .env"
        )
    return create_engine(
        f"mysql+pymysql://{user}:{password}@{host}/",
        pool_recycle=3600,
        connect_args={"connect_timeout": 15},
    )


# =============================================================================
# 3. SQL QUERIES
# =============================================================================

def build_vendor_inbound_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Vendor inbound volume: qty_received, po_sku, spec/packaging errors from batch."""
    date_clause = (
        f"ibb.in_dtm >= UNIX_TIMESTAMP('{start_date.isoformat()}')\n"
        f"      AND ibb.in_dtm < UNIX_TIMESTAMP('{end_date.isoformat()}')"
    )
    wh = ""
    if warehouse == "LA":
        wh = "AND ib.warehouse_number = 001"
    elif warehouse == "NJ":
        wh = "AND ib.warehouse_number = 002"

    return f"""
SELECT
    bb.vendor_name, bb.vendor_id, 'Vendor' AS business_type, bb.team,
    COUNT(DISTINCT bb.reference_id) AS po_received,
    SUM(bb.quantity) AS qty_received,
    COUNT(bb.item_number) AS po_sku_received,
    SUM(bb.weight_error) AS spec_image_error,
    SUM(CASE WHEN bb.problem_report IS NOT NULL AND bb.problem_report != '' THEN 1 ELSE 0 END) AS packaging_error
FROM (
    SELECT ib.reference_id, ib.inbound_number, ibb.item_number, ibb.quantity,
        pv.vendor_name, ib.warehouse_number, pv.vendor_id,
        ibb.image_error, ibb.weight_error, ibb.problem_report,
        CASE
            WHEN c1.category_id IN (1, 301, 310) THEN 'Food'
            WHEN c1.category_id IN (2, 7, 10, 11, 320, 334, 342, 350) THEN 'Non-food'
            ELSE 'Other'
        END AS team
    FROM yamibuy_wh.wh_inbound_batch ibb
    LEFT JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
    LEFT JOIN yamibuy_po.po_purchase_order ppo ON ppo.po_number = ib.reference_id
    LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
    LEFT JOIN yamibuy_im.im_item ii ON ii.item_number = ibb.item_number
    LEFT JOIN yamibuy_im.im_category c3 ON c3.category_id = ii.category_id
    LEFT JOIN yamibuy_im.im_category c2 ON c2.category_id = c3.parent_category_id
    LEFT JOIN yamibuy_im.im_category c1 ON c1.category_id = c2.parent_category_id
    WHERE ib.reference_id NOT LIKE 'F%'
      AND ibb.item_number NOT LIKE '8%'
      AND {date_clause}
      {wh}
) bb
WHERE bb.vendor_name IS NOT NULL
GROUP BY 1, 2, 3, 4
"""


def build_seller_inbound_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Not used in Vendor-only mode."""
    pass


def build_vendor_bpm_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Vendor BPM issues (criteria 1-6): damage, exp, overage, upc, po, no_data."""
    date_clause = (
        f"bpm.in_dtm >= UNIX_TIMESTAMP('{start_date.isoformat()}')\n"
        f"  AND bpm.in_dtm < UNIX_TIMESTAMP('{end_date.isoformat()}')"
    )
    wh = ""
    if warehouse == "LA":
        wh = "AND bpm.warehouse_number = 001"
    elif warehouse == "NJ":
        wh = "AND bpm.warehouse_number = 002"

    return f"""
SELECT
    pv.vendor_name, bpm.vendor_id, 'Vendor' AS business_type,
    SUM(CASE WHEN bpm.problem_type = 4 THEN bpm.item_qty ELSE 0 END) AS overage_qty,
    SUM(CASE WHEN bpm.problem_type = 3 THEN bpm.item_qty ELSE 0 END) AS damage_qty,
    SUM(CASE WHEN bpm.problem_type IN (5, 6) THEN bpm.item_qty ELSE 0 END) AS upc_qty,
    SUM(CASE WHEN bpm.problem_type IN (1, 2) THEN bpm.item_qty ELSE 0 END) AS exp_qty,
    SUM(CASE WHEN bpm.problem_type IN (7, 8, 9) THEN 1 ELSE 0 END) AS po_qty,
    SUM(CASE WHEN bpm.problem_type = 10 THEN bpm.item_qty ELSE 0 END) AS no_data_qty
FROM yamibuy_wh.wh_problem_solving_bpm bpm
LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = bpm.vendor_id
WHERE bpm.create_type = 1
  AND bpm.business_type = 1
  AND {date_clause}
  {wh}
  AND pv.vendor_name IS NOT NULL
  AND pv.vendor_name NOT LIKE '%测试%'
GROUP BY 1, 2, 3
"""


def build_seller_bpm_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Not used in Vendor-only mode."""
    pass


def build_vendor_qc_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Vendor QC random check (criteria 10: poor_quality)."""
    date_clause = (
        f"bpm.in_dtm >= UNIX_TIMESTAMP('{start_date.isoformat()}')\n"
        f"  AND bpm.in_dtm < UNIX_TIMESTAMP('{end_date.isoformat()}')"
    )
    wh = ""
    if warehouse == "LA":
        wh = "AND bpm.warehouse_number = 001"
    elif warehouse == "NJ":
        wh = "AND bpm.warehouse_number = 002"

    return f"""
SELECT
    pv.vendor_name, bpm.vendor_id, 'Vendor' AS business_type,
    SUM(CASE WHEN bpm.comment LIKE '%poor quality%' THEN bpm.item_qty ELSE 0 END) AS poor_quality_qty
FROM yamibuy_wh.wh_problem_solving_bpm bpm
LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = bpm.vendor_id
WHERE bpm.create_type = 2
  AND bpm.business_type = 1
  AND bpm.problem_type IN (3, 6)
  AND {date_clause}
  {wh}
  AND pv.vendor_name IS NOT NULL
  AND pv.vendor_name NOT LIKE '%测试%'
GROUP BY 1, 2, 3
"""


def build_seller_qc_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Not used in Vendor-only mode."""
    pass


def build_seller_responsiveness_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Not used in Vendor-only mode (Vendor responsiveness weight = 0%)."""
    pass


# =============================================================================
# 4. DATA LOADING
# =============================================================================

def load_all_data(start_date: date, end_date: date, warehouse: str = "All") -> pd.DataFrame:
    """Load Vendor-only raw data from MySQL and merge into a single DataFrame with rates."""
    engine = get_engine()

    print(f"  Loading Vendor inbound volume data...")
    with engine.connect() as conn:
        inbound_df = pd.read_sql(text(build_vendor_inbound_sql(start_date, end_date, warehouse)), conn)
    print(f"    → {len(inbound_df)} inbound records")

    print(f"  Loading Vendor BPM issue data...")
    with engine.connect() as conn:
        bpm_df = pd.read_sql(text(build_vendor_bpm_sql(start_date, end_date, warehouse)), conn)
    print(f"    → {len(bpm_df)} BPM records")

    print(f"  Loading Vendor QC data...")
    with engine.connect() as conn:
        qc_df = pd.read_sql(text(build_vendor_qc_sql(start_date, end_date, warehouse)), conn)
    print(f"    → {len(qc_df)} QC records")

    # --- Merge and compute rates ---
    print(f"  Computing rates...")
    merge_keys = ["vendor_id", "business_type"]

    # Keep dominant team per vendor
    team_lookup = (
        inbound_df.sort_values("qty_received", ascending=False)
        .drop_duplicates(subset=merge_keys, keep="first")[merge_keys + ["vendor_name", "team"]]
    )

    # Aggregate inbound to vendor level
    inbound_agg = (
        inbound_df.groupby(merge_keys, as_index=False)
        .agg({
            "vendor_name": "first",
            "po_received": "sum",
            "qty_received": "sum",
            "po_sku_received": "sum",
            "spec_image_error": "sum",
            "packaging_error": "sum",
        })
    )
    inbound_agg = inbound_agg.merge(team_lookup[merge_keys + ["team"]], on=merge_keys, how="left")

    # Merge BPM
    df = inbound_agg.merge(
        bpm_df[merge_keys + ["overage_qty", "damage_qty", "upc_qty", "exp_qty", "po_qty", "no_data_qty"]],
        on=merge_keys, how="left",
    )

    # Merge QC
    df = df.merge(qc_df[merge_keys + ["poor_quality_qty"]], on=merge_keys, how="left")

    # Fill NaN numerators
    numerator_cols = ["overage_qty", "damage_qty", "upc_qty", "exp_qty", "po_qty", "no_data_qty", "poor_quality_qty"]
    df[numerator_cols] = df[numerator_cols].fillna(0)

    # Compute rates
    qty = df["qty_received"].replace(0, pd.NA)
    sku_qty = df["po_sku_received"].replace(0, pd.NA)

    df["damage_rate"] = (df["damage_qty"] / qty).fillna(0)
    df["exp_error_rate"] = (df["exp_qty"] / qty).fillna(0)
    df["overage_rate"] = (df["overage_qty"] / qty).fillna(0)
    df["upc_error_rate"] = (df["upc_qty"] / qty).fillna(0)
    df["no_data_rate"] = (df["no_data_qty"] / qty).fillna(0)
    df["poor_quality_rate"] = (df["poor_quality_qty"] / qty).fillna(0)
    df["spec_image_error_rate"] = (df["spec_image_error"] / sku_qty).fillna(0)
    df["packaging_error_rate"] = (df["packaging_error"] / sku_qty).fillna(0)
    df["po_error_rate"] = (df["po_qty"] / sku_qty).fillna(0)

    # Responsiveness = 0 for Vendor (weight is 0% anyway)
    df["responsiveness_days"] = 0.0

    print(f"    → {len(df)} vendors with rates computed")
    return df


# =============================================================================
# 5. SCORING ENGINE
# =============================================================================

def compute_grade(rate: float, thresholds: dict) -> int:
    """
    Map a rate to a grade {100, 80, 60, 20}.
    Lower rate = better grade.
    """
    if rate <= thresholds['A']:
        return 100
    elif rate <= thresholds['B']:
        return 80
    elif rate <= thresholds['C']:
        return 60
    else:
        return 20


def classify_tier(score: float) -> str:
    """Assign tier A/B/C/D based on total score."""
    if score >= TIER_BOUNDARIES['A']:
        return 'A'
    elif score >= TIER_BOUNDARIES['B']:
        return 'B'
    elif score >= TIER_BOUNDARIES['C']:
        return 'C'
    else:
        return 'D'


def compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute grades for each criteria and calculate weighted total score.

    For each vendor/seller row:
      1. Get the rate for each criteria
      2. Convert to grade (100/80/60/20) using thresholds
      3. Multiply by weight and sum → total_score (0-100)
      4. Classify into tier A/B/C/D

    Returns DataFrame with added columns:
      - grade_{criteria} for each of 10 criteria
      - total_score (float, 0-100)
      - tier (str, A/B/C/D)
    """
    result = df.copy()

    # Initialize grade columns
    for criteria in CRITERIA_NAMES:
        result[f'grade_{criteria}'] = 0

    result['total_score'] = 0.0

    for idx, row in result.iterrows():
        business_type = row['business_type']
        btype_weights = WEIGHTS[business_type]
        btype_thresholds = THRESHOLDS[business_type]

        total = 0.0
        for criteria in CRITERIA_NAMES:
            # Get rate value
            if criteria == 'responsiveness':
                rate = row['responsiveness_days']
            else:
                rate = row[f'{criteria}_rate']

            # Compute grade
            grade = compute_grade(rate, btype_thresholds[criteria])
            result.at[idx, f'grade_{criteria}'] = grade

            # Weighted contribution
            total += grade * btype_weights[criteria]

        result.at[idx, 'total_score'] = total

    # Assign tier
    result['tier'] = result['total_score'].apply(classify_tier)

    return result


# =============================================================================
# 6. OWNER INFO (PM for Vendor, AM for Seller)
# =============================================================================

def load_owner_info(engine, df: pd.DataFrame) -> pd.DataFrame:
    """
    Load PM owner info for Vendors using po_pm_vendor + po_pm_team (domain-aware).
    Each vendor gets exactly ONE PM.
    Priority: is_primary=1 in matching domain > any PM in matching domain > is_primary=1 any domain > first PM
    Fallback: Food→janelle.zhang, Non-food→jillian.ji
    Adds column: pm_am (str)
    """
    df["pm_am"] = ""

    with engine.connect() as conn:
        vendor_ids = df["vendor_id"].unique()
        if len(vendor_ids) > 0:
            pm_df = pd.read_sql(text("""
                SELECT pv.vendor_id, pm.PM_name AS pm_name, pv.is_primary, pt.domain
                FROM yamibuy_po.po_pm_vendor pv
                JOIN yamibuy_im.im_pm pm ON pm.PM_id = CAST(pv.pm_id AS CHAR)
                LEFT JOIN yamibuy_po.po_pm_team pt ON pt.pm_id = pm.PM_id AND pt.deleted = 0
                WHERE pv.deleted = 0 AND pm.status = 'A'
            """), conn)

            if not pm_df.empty:
                pm_df = pm_df.drop_duplicates(subset=["vendor_id", "pm_name", "domain"])
                team_to_domain = {"Food": 0, "Non-food": 1, "Other": None}

                for vid in vendor_ids:
                    vid_rows = pm_df[pm_df["vendor_id"] == vid]
                    if vid_rows.empty:
                        continue

                    vendor_team = df.loc[df["vendor_id"] == vid, "team"].iloc[0]
                    target_domain = team_to_domain.get(vendor_team)
                    pm_name = None

                    if target_domain is not None:
                        match = vid_rows[(vid_rows["domain"] == target_domain) & (vid_rows["is_primary"] == 1)]
                        if not match.empty:
                            pm_name = match.iloc[0]["pm_name"]
                        else:
                            match = vid_rows[vid_rows["domain"] == target_domain]
                            if not match.empty:
                                pm_name = sorted(match["pm_name"].unique())[0]

                    if pm_name is None:
                        match = vid_rows[vid_rows["is_primary"] == 1]
                        if not match.empty:
                            pm_name = match.iloc[0]["pm_name"]
                        else:
                            pm_name = sorted(vid_rows["pm_name"].unique())[0]

                    df.loc[df["vendor_id"] == vid, "pm_am"] = pm_name

        # Fallback for vendors with no PM record
        no_pm_mask = (df["pm_am"] == "") | df["pm_am"].isna()
        if no_pm_mask.any():
            df.loc[no_pm_mask & (df["team"] == "Food"), "pm_am"] = "janelle.zhang"
            df.loc[no_pm_mask & (df["team"] == "Non-food"), "pm_am"] = "jillian.ji"
            df.loc[no_pm_mask & (df["team"] == "Other"), "pm_am"] = "janelle.zhang"

    return df


# =============================================================================
# 7. OUTPUT FORMATTING (matches Detail Page display)
# =============================================================================

def format_output(df: pd.DataFrame) -> pd.DataFrame:
    """
    Format the scored DataFrame for output.
    Columns match the Simulator Detail Page view.
    """
    # Column order matching Detail tab
    output_cols = [
        "tier", "total_score", "vendor_name", "vendor_id",
        "business_type", "team", "pm_am",
        "qty_received", "po_sku_received",
        # Rate percentages
        "damage_rate", "exp_error_rate", "overage_rate",
        "spec_image_error_rate", "no_data_rate", "upc_error_rate",
        "packaging_error_rate", "po_error_rate", "responsiveness_days", "poor_quality_rate",
        # Grades
        "grade_damage", "grade_exp_error", "grade_overage",
        "grade_spec_image_error", "grade_no_data", "grade_upc_error",
        "grade_packaging_error", "grade_po_error", "grade_responsiveness", "grade_poor_quality",
        # Raw quantities
        "damage_qty", "exp_qty", "overage_qty",
        "spec_image_error", "no_data_qty", "upc_qty",
        "packaging_error", "po_qty", "poor_quality_qty",
    ]

    # Only include columns that exist
    available = [c for c in output_cols if c in df.columns]
    result = df[available].copy()

    # Sort: Tier A first, then by score descending
    tier_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    result["_tier_rank"] = result["tier"].map(tier_order)
    result = result.sort_values(["_tier_rank", "total_score"], ascending=[True, False])
    result = result.drop(columns=["_tier_rank"])

    # Rename for readability
    result = result.rename(columns={
        "tier": "Tier",
        "total_score": "Total Score",
        "vendor_name": "Vendor/Seller Name",
        "vendor_id": "ID",
        "business_type": "Type",
        "team": "Team",
        "pm_am": "PM/AM",
        "qty_received": "Qty Received",
        "po_sku_received": "PO SKU Received",
        "damage_rate": "Damage Rate",
        "exp_error_rate": "Exp Error Rate",
        "overage_rate": "Overage Rate",
        "spec_image_error_rate": "Spec/Image Rate",
        "no_data_rate": "Wrong Items Rate",
        "upc_error_rate": "UPC Error Rate",
        "packaging_error_rate": "Packaging Rate",
        "po_error_rate": "PO Error Rate",
        "responsiveness_days": "Responsiveness (days)",
        "poor_quality_rate": "QC Issue Rate",
    })

    return result


# =============================================================================
# 8. MAIN EXECUTION
# =============================================================================

def main():
    """
    Main execution:
    1. Load data from MySQL (past 180 days)
    2. Compute rates
    3. Score each vendor/seller
    4. Load owner info
    5. Export to CSV
    """
    print("=" * 60)
    print("Inbound Quality Score Calculator — VENDOR ONLY")
    print("=" * 60)

    # Parameters
    end_date = date.today()
    start_date = end_date - timedelta(days=180)
    warehouse = "All"  # Options: "All", "LA", "NJ"

    print(f"\nParameters:")
    print(f"  Date Range: {start_date} → {end_date} ({(end_date - start_date).days} days)")
    print(f"  Warehouse: {warehouse}")
    print(f"  Tier Boundaries: A≥{TIER_BOUNDARIES['A']}, B≥{TIER_BOUNDARIES['B']}, C≥{TIER_BOUNDARIES['C']}")
    print()

    # Step 1: Load data
    print("[1/4] Loading data from database...")
    df = load_all_data(start_date, end_date, warehouse)

    # Step 2: Compute scores
    print("\n[2/4] Computing scores...")
    df = compute_scores(df)
    tier_counts = df["tier"].value_counts()
    print(f"  Tier distribution: A={tier_counts.get('A', 0)}, B={tier_counts.get('B', 0)}, "
          f"C={tier_counts.get('C', 0)}, D={tier_counts.get('D', 0)}")
    print(f"  Average score: {df['total_score'].mean():.1f}")

    # Step 3: Load owner info
    print("\n[3/4] Loading owner info (PM/AM)...")
    try:
        engine = get_engine()
        df = load_owner_info(engine, df)
        print("  ✓ Owner info loaded")
    except Exception as e:
        print(f"  ⚠ Owner info failed: {e}")
        df["pm_am"] = ""

    # Step 4: Format and export
    print("\n[4/4] Formatting and exporting...")
    output_df = format_output(df)

    # Save to CSV
    output_file = Path(__file__).parent / f"vendor_quality_scores_{end_date.isoformat()}.csv"
    output_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"  ✓ Exported to: {output_file}")
    print(f"  Total records: {len(output_df)}")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)

    return output_df


if __name__ == "__main__":
    main()
