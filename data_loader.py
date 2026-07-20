"""
Data Loader module for the Inbound Quality Score Simulator.

Connects to the MySQL database and retrieves aggregated inbound quality metrics
for Vendors and Sellers over a 180-day window. Computes error rates by merging
inbound volume data with BPM problem ticket data.

Two separate SQL paths handle Vendor (po_vendor JOIN, reference_id NOT LIKE 'F%')
and Seller (wh_seller_shipment JOIN, reference_id LIKE 'F%') data.
"""

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from config import REQUIRED_CSV_COLUMNS

# .env location — try project directory first, fall back to Windows path
ENV_PATH = Path(__file__).parent / ".env"
if not ENV_PATH.exists():
    ENV_PATH = Path(
        r"C:\Users\ziyi.fang\OneDrive - YAMIBUY.COM\Documents\Ziyi\Project\config\.env"
    )


def _get_engine():
    """Create SQLAlchemy engine from .env credentials."""
    # Load from both project .env and OneDrive fallback (override=True to ensure DB creds load)
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASS")
    host = os.getenv("MYSQL_HOST")
    if not all([user, password, host]):
        raise EnvironmentError(
            "Missing database credentials. Ensure MYSQL_USER, MYSQL_PASS, "
            "and MYSQL_HOST are set in .env file."
        )
    engine = create_engine(
        f"mysql+pymysql://{user}:{password}@{host}/",
        pool_recycle=3600,
        connect_args={"connect_timeout": 15},
    )
    return engine


# ---------------------------------------------------------------------------
# SQL Query Definitions (parameterized by date range)
# ---------------------------------------------------------------------------


def _date_filter_clause(start_date: date, end_date: date) -> str:
    """Generate SQL timestamp range clause for in_dtm field."""
    return (
        f"ibb.in_dtm >= UNIX_TIMESTAMP('{start_date.isoformat()}')\n"
        f"      AND ibb.in_dtm < UNIX_TIMESTAMP('{end_date.isoformat()}')"
    )


def _bpm_date_filter_clause(start_date: date, end_date: date) -> str:
    """Generate SQL timestamp range clause for BPM in_dtm field."""
    return (
        f"bpm.in_dtm >= UNIX_TIMESTAMP('{start_date.isoformat()}')\n"
        f"  AND bpm.in_dtm < UNIX_TIMESTAMP('{end_date.isoformat()}')"
    )


def _warehouse_filter_inbound(warehouse: str) -> str:
    """Generate warehouse filter for inbound queries. Empty string = no filter."""
    if warehouse == "LA":
        return "AND ib.warehouse_number = 001"
    elif warehouse == "NJ":
        return "AND ib.warehouse_number = 002"
    return ""  # All


def _warehouse_filter_bpm(warehouse: str) -> str:
    """Generate warehouse filter for BPM queries. Empty string = no filter."""
    if warehouse == "LA":
        return "AND bpm.warehouse_number = 001"
    elif warehouse == "NJ":
        return "AND bpm.warehouse_number = 002"
    return ""  # All


def _build_vendor_inbound_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Build Vendor inbound volume SQL with parameterized date range and warehouse."""
    date_clause = _date_filter_clause(start_date, end_date)
    wh_filter = _warehouse_filter_inbound(warehouse)
    return f"""
SELECT
    bb.vendor_name,
    bb.vendor_id,
    'Vendor' AS business_type,
    bb.team,
    COUNT(DISTINCT bb.reference_id) AS po_received,
    SUM(bb.quantity) AS qty_received,
    COUNT(bb.item_number) AS po_sku_received,
    SUM(bb.weight_error) AS spec_image_error,
    SUM(CASE WHEN bb.problem_report IS NOT NULL AND bb.problem_report != '' THEN 1 ELSE 0 END) AS packaging_error
FROM (
    SELECT
        ib.reference_id,
        ib.inbound_number,
        ibb.item_number,
        ibb.quantity,
        pv.vendor_name,
        ib.warehouse_number,
        pv.vendor_id,
        ibb.image_error,
        ibb.weight_error,
        ibb.problem_report,
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
      {wh_filter}
) bb
WHERE bb.vendor_name IS NOT NULL
GROUP BY 1, 2, 3, 4
"""


def _build_seller_inbound_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Build Seller inbound volume SQL with parameterized date range and warehouse."""
    date_clause = _date_filter_clause(start_date, end_date)
    wh_filter = _warehouse_filter_inbound(warehouse)
    return f"""
SELECT
    bb.vendor_name,
    bb.vendor_id,
    'Seller' AS business_type,
    'TTL' AS team,
    COUNT(DISTINCT bb.reference_id) AS po_received,
    SUM(bb.quantity) AS qty_received,
    COUNT(bb.item_number) AS po_sku_received,
    SUM(CASE WHEN bb.weight_error = 1 OR bb.image_error = 1 THEN 1 ELSE 0 END) AS spec_image_error,
    SUM(CASE WHEN bb.problem_report IS NOT NULL AND bb.problem_report != '' THEN 1 ELSE 0 END) AS packaging_error
FROM (
    SELECT
        ib.reference_id,
        ib.inbound_number,
        ibb.item_number,
        ibb.quantity,
        seller.vendor_name,
        ib.warehouse_number,
        wss.seller_id AS vendor_id,
        ibb.image_error,
        ibb.weight_error,
        ibb.problem_report
    FROM yamibuy_wh.wh_inbound_batch ibb
    LEFT JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
    LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = ib.reference_id
    LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = wss.seller_id
    WHERE ib.reference_id LIKE 'F%'
      AND {date_clause}
      {wh_filter}
) bb
WHERE bb.vendor_name IS NOT NULL
GROUP BY 1, 2, 3, 4
"""


def _build_vendor_bpm_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Build Vendor BPM SQL using bpm.vendor_id directly."""
    date_clause = _bpm_date_filter_clause(start_date, end_date)
    wh_filter = _warehouse_filter_bpm(warehouse)
    return f"""
SELECT
    pv.vendor_name,
    bpm.vendor_id,
    'Vendor' AS business_type,
    SUM(CASE WHEN bpm.problem_type = 4 THEN bpm.item_qty ELSE 0 END) AS overage_qty,
    SUM(CASE WHEN bpm.problem_type = 3 THEN bpm.item_qty ELSE 0 END) AS damage_qty,
    SUM(CASE WHEN bpm.problem_type IN (5, 6) THEN bpm.item_qty ELSE 0 END) AS upc_qty,
    SUM(CASE WHEN bpm.problem_type IN (1, 2) THEN bpm.item_qty ELSE 0 END) AS exp_qty,
    SUM(CASE WHEN bpm.problem_type IN (7, 8, 9) THEN bpm.item_qty ELSE 0 END) AS po_qty,
    SUM(CASE WHEN bpm.problem_type = 10 THEN bpm.item_qty ELSE 0 END) AS no_data_qty
FROM yamibuy_wh.wh_problem_solving_bpm bpm
LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = bpm.vendor_id
WHERE bpm.create_type = 1
  AND bpm.business_type = 1
  AND {date_clause}
  {wh_filter}
  AND pv.vendor_name IS NOT NULL
  AND pv.vendor_name NOT LIKE '%测试%'
GROUP BY 1, 2, 3
"""


def _build_seller_bpm_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Build Seller BPM SQL using bpm.vendor_id directly."""
    date_clause = _bpm_date_filter_clause(start_date, end_date)
    wh_filter = _warehouse_filter_bpm(warehouse)
    return f"""
SELECT
    seller.vendor_name,
    bpm.vendor_id,
    'Seller' AS business_type,
    SUM(CASE WHEN bpm.problem_type = 4 THEN bpm.item_qty ELSE 0 END) AS overage_qty,
    SUM(CASE WHEN bpm.problem_type = 3 THEN bpm.item_qty ELSE 0 END) AS damage_qty,
    SUM(CASE WHEN bpm.problem_type IN (5, 6) THEN bpm.item_qty ELSE 0 END) AS upc_qty,
    SUM(CASE WHEN bpm.problem_type IN (1, 2) THEN bpm.item_qty ELSE 0 END) AS exp_qty,
    SUM(CASE WHEN bpm.problem_type IN (7, 8, 9) THEN bpm.item_qty ELSE 0 END) AS po_qty,
    SUM(CASE WHEN bpm.problem_type = 10 THEN bpm.item_qty ELSE 0 END) AS no_data_qty
FROM yamibuy_wh.wh_problem_solving_bpm bpm
LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = bpm.vendor_id
WHERE bpm.create_type = 1
  AND bpm.business_type = 5
  AND {date_clause}
  {wh_filter}
  AND seller.vendor_name IS NOT NULL
  AND seller.vendor_name NOT LIKE '%测试%'
GROUP BY 1, 2, 3
"""


def _build_vendor_qc_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Build Vendor QC SQL using bpm.vendor_id directly."""
    date_clause = _bpm_date_filter_clause(start_date, end_date)
    wh_filter = _warehouse_filter_bpm(warehouse)
    return f"""
SELECT
    pv.vendor_name,
    bpm.vendor_id,
    'Vendor' AS business_type,
    SUM(CASE WHEN bpm.comment LIKE '%quality%' THEN bpm.item_qty ELSE 0 END) AS poor_quality_qty
FROM yamibuy_wh.wh_problem_solving_bpm bpm
LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = bpm.vendor_id
WHERE bpm.create_type = 2
  AND bpm.business_type = 1
  AND bpm.problem_type = 3
  AND {date_clause}
  {wh_filter}
  AND pv.vendor_name IS NOT NULL
  AND pv.vendor_name NOT LIKE '%测试%'
GROUP BY 1, 2, 3
"""


def _build_seller_qc_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """Build Seller QC SQL using bpm.vendor_id directly."""
    date_clause = _bpm_date_filter_clause(start_date, end_date)
    wh_filter = _warehouse_filter_bpm(warehouse)
    return f"""
SELECT
    seller.vendor_name,
    bpm.vendor_id,
    'Seller' AS business_type,
    SUM(CASE WHEN bpm.comment LIKE '%quality%' THEN bpm.item_qty ELSE 0 END) AS poor_quality_qty
FROM yamibuy_wh.wh_problem_solving_bpm bpm
LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = bpm.vendor_id
WHERE bpm.create_type = 2
  AND bpm.business_type = 5
  AND bpm.problem_type = 3
  AND {date_clause}
  {wh_filter}
  AND seller.vendor_name IS NOT NULL
  AND seller.vendor_name NOT LIKE '%测试%'
GROUP BY 1, 2, 3
"""


def _build_seller_responsiveness_sql(start_date: date, end_date: date, warehouse: str = "All") -> str:
    """
    Build Seller Responsiveness SQL — average hours from BPM creation to processing.
    Uses TIMESTAMPDIFF(HOUR, FROM_UNIXTIME(in_dtm), FROM_UNIXTIME(edit_dtm)).
    Only counts tickets where edit_dtm > in_dtm (i.e., actually processed).
    """
    date_clause = _bpm_date_filter_clause(start_date, end_date)
    wh_filter = _warehouse_filter_bpm(warehouse)
    return f"""
SELECT
    bpm.vendor_id,
    seller.vendor_name,
    'Seller' AS business_type,
    AVG(TIMESTAMPDIFF(HOUR, FROM_UNIXTIME(bpm.in_dtm), FROM_UNIXTIME(bpm.edit_dtm))) AS responsiveness_hours
FROM yamibuy_wh.wh_problem_solving_bpm bpm
LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = bpm.vendor_id
WHERE bpm.business_type = 5
  AND bpm.create_type = 1
  AND bpm.edit_dtm > bpm.in_dtm
  AND {date_clause}
  {wh_filter}
  AND seller.vendor_name IS NOT NULL
  AND seller.vendor_name NOT LIKE '%测试%'
GROUP BY 1, 2, 3
"""


# ---------------------------------------------------------------------------
# Data Loading Functions
# ---------------------------------------------------------------------------


def _load_inbound_volume(engine, start_date: date, end_date: date, warehouse: str = "All") -> pd.DataFrame:
    """Load inbound volume data for both Vendor and Seller paths."""
    with engine.connect() as conn:
        vendor_df = pd.read_sql(text(_build_vendor_inbound_sql(start_date, end_date, warehouse)), conn)
        seller_df = pd.read_sql(text(_build_seller_inbound_sql(start_date, end_date, warehouse)), conn)
    df = pd.concat([vendor_df, seller_df], ignore_index=True)
    return df


def _load_bpm_data(engine, start_date: date, end_date: date, warehouse: str = "All") -> pd.DataFrame:
    """Load BPM problem ticket data for criteria 1-6 (both Vendor and Seller)."""
    with engine.connect() as conn:
        vendor_bpm = pd.read_sql(text(_build_vendor_bpm_sql(start_date, end_date, warehouse)), conn)
        seller_bpm = pd.read_sql(text(_build_seller_bpm_sql(start_date, end_date, warehouse)), conn)
    df = pd.concat([vendor_bpm, seller_bpm], ignore_index=True)
    return df


def _load_qc_data(engine, start_date: date, end_date: date, warehouse: str = "All") -> pd.DataFrame:
    """Load QC random check data for criteria 9 (both Vendor and Seller)."""
    with engine.connect() as conn:
        vendor_qc = pd.read_sql(text(_build_vendor_qc_sql(start_date, end_date, warehouse)), conn)
        seller_qc = pd.read_sql(text(_build_seller_qc_sql(start_date, end_date, warehouse)), conn)
    df = pd.concat([vendor_qc, seller_qc], ignore_index=True)
    return df


def _load_responsiveness_data(engine, start_date: date, end_date: date, warehouse: str = "All") -> pd.DataFrame:
    """Load Seller responsiveness (avg processing hours). Vendors default to 0."""
    with engine.connect() as conn:
        seller_resp = pd.read_sql(
            text(_build_seller_responsiveness_sql(start_date, end_date, warehouse)), conn
        )
    return seller_resp


def _compute_rates(inbound_df: pd.DataFrame, bpm_df: pd.DataFrame,
                   qc_df: pd.DataFrame, resp_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Merge inbound volume with BPM and QC data, then compute error rates.

    Rate formulas:
    - Criteria 1-6, 9: numerator / qty_received (handle div-by-zero with fillna(0))
    - Criteria 7 (spec_image): spec_image_error / po_sku_received
    - Criteria 8 (packaging): packaging_error / po_sku_received
    """
    # Merge keys: vendor_id + business_type (no warehouse — aggregated at vendor level)
    merge_keys = ["vendor_id", "business_type"]

    # A Vendor may have both Food and Non-food rows (grouped by team in SQL).
    # BPM/QC data does NOT split by team, so we must aggregate inbound to the
    # same granularity before merging. We keep the team with the most qty_received.
    team_lookup = (
        inbound_df.sort_values("qty_received", ascending=False)
        .drop_duplicates(subset=merge_keys, keep="first")[merge_keys + ["vendor_name", "team"]]
    )

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
    # Re-attach the dominant team
    inbound_agg = inbound_agg.merge(
        team_lookup[merge_keys + ["team"]], on=merge_keys, how="left"
    )

    # Merge BPM data onto aggregated inbound volume
    df = inbound_agg.merge(
        bpm_df[merge_keys + [
            "overage_qty", "damage_qty", "upc_qty",
            "exp_qty", "po_qty", "no_data_qty"
        ]],
        on=merge_keys,
        how="left",
    )

    # Merge QC data onto combined dataframe
    df = df.merge(
        qc_df[merge_keys + ["poor_quality_qty"]],
        on=merge_keys,
        how="left",
    )

    # Fill NaN numerators with 0 (vendors with no BPM issues)
    numerator_cols = [
        "overage_qty", "damage_qty", "upc_qty",
        "exp_qty", "po_qty", "no_data_qty", "poor_quality_qty",
    ]
    df[numerator_cols] = df[numerator_cols].fillna(0)

    # Compute rates — criteria 1-6, 9 use qty_received as denominator
    # Handle division by zero: if qty_received is 0, rate stays 0
    qty = df["qty_received"].replace(0, pd.NA)
    df["overage_rate"] = (df["overage_qty"] / qty).fillna(0)
    df["damage_rate"] = (df["damage_qty"] / qty).fillna(0)
    df["upc_error_rate"] = (df["upc_qty"] / qty).fillna(0)
    df["exp_error_rate"] = (df["exp_qty"] / qty).fillna(0)
    df["po_error_rate"] = (df["po_qty"] / qty).fillna(0)
    df["no_data_rate"] = (df["no_data_qty"] / qty).fillna(0)
    df["poor_quality_rate"] = (df["poor_quality_qty"] / qty).fillna(0)

    # Criteria 7-8 use po_sku_received as denominator
    sku_qty = df["po_sku_received"].replace(0, pd.NA)
    df["spec_image_error_rate"] = (df["spec_image_error"] / sku_qty).fillna(0)
    df["packaging_error_rate"] = (df["packaging_error"] / sku_qty).fillna(0)

    # Responsiveness: average days from BPM creation to last edit (Seller only)
    # Vendor defaults to 0 (this criteria has 0% weight for Vendors)
    df["responsiveness_days"] = 0.0

    return df


def _select_output_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Select and order the final output columns matching the interface spec."""
    output_columns = [
        "vendor_id",
        "vendor_name",
        "business_type",
        "team",
        "qty_received",
        "po_sku_received",
        "overage_rate",
        "damage_rate",
        "upc_error_rate",
        "exp_error_rate",
        "po_error_rate",
        "no_data_rate",
        "spec_image_error_rate",
        "packaging_error_rate",
        "poor_quality_rate",
        "responsiveness_days",
        # Raw numerator columns for "Actual Cases" display mode
        "overage_qty",
        "damage_qty",
        "upc_qty",
        "exp_qty",
        "po_qty",
        "no_data_qty",
        "spec_image_error",
        "packaging_error",
        "poor_quality_qty",
    ]
    # Ensure all columns exist
    for col in output_columns:
        if col not in df.columns:
            df[col] = 0
    return df[output_columns].copy()


def _load_owner_info(engine, df: pd.DataFrame) -> pd.DataFrame:
    """
    Load PM (for Vendor) and AM (for Seller) owner info.

    Each vendor/seller gets exactly ONE owner assigned:
    - Vendor: from po_pm_vendor + po_pm_team (domain-aware matching)
      Logic: match vendor's team (Food/Non-food) to PM's domain (0=Food, 1=Non-food)
      Priority: is_primary=1 in matching domain > any PM in matching domain > is_primary=1 any domain > first PM
    - Seller: from local CSV cache (seller_am.csv)

    Adds column: pm_am (str) — the single PM or AM name
    """
    df["pm_am"] = ""

    def _normalize_am_name(name):
        """Normalize AM name to first-name only, lowercase.
        'jax.qian' → 'jax', 'irene.yu' → 'irene', 'Celia.Liang' → 'celia'
        """
        if not name or not isinstance(name, str):
            return ""
        name = name.strip().lower()
        name = name.split("@")[0]
        if "." in name:
            return name.split(".")[0]
        elif " " in name:
            return name.split(" ")[0]
        return name

    with engine.connect() as conn:
        # --- Vendor PM (domain-aware) ---
        vendor_ids = df.loc[df["business_type"] == "Vendor", "vendor_id"].unique()
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
                vendor_mask = df["business_type"] == "Vendor"
                team_to_domain = {"Food": 0, "Non-food": 1, "Other": None}

                for vid in df.loc[vendor_mask, "vendor_id"].unique():
                    vid_rows = pm_df[pm_df["vendor_id"] == vid]
                    if vid_rows.empty:
                        continue

                    vendor_team = df.loc[vendor_mask & (df["vendor_id"] == vid), "team"].iloc[0]
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

                    df.loc[vendor_mask & (df["vendor_id"] == vid), "pm_am"] = pm_name

            # Fallback for vendors with no PM record at all
            no_pm_mask = vendor_mask & ((df["pm_am"] == "") | df["pm_am"].isna())
            if no_pm_mask.any():
                df.loc[no_pm_mask & (df["team"] == "Food"), "pm_am"] = "janelle.zhang"
                df.loc[no_pm_mask & (df["team"] == "Non-food"), "pm_am"] = "jillian.ji"
                df.loc[no_pm_mask & (df["team"] == "Other"), "pm_am"] = "janelle.zhang"

    # --- Seller AM (from local CSV cache — sourced from dwb_bi_vendor_region_info) ---
    seller_ids = df.loc[df["business_type"] == "Seller", "vendor_id"].unique()
    if len(seller_ids) > 0:
        cache_file = Path(__file__).parent / "cache" / "seller_am.csv"
        if cache_file.exists():
            am_df = pd.read_csv(cache_file)
            am_df = am_df.dropna(subset=["seller_id", "am_name"])
            am_df["seller_id"] = am_df["seller_id"].astype(int)
            seller_mask = df["business_type"] == "Seller"
            for sid in df.loc[seller_mask, "vendor_id"].unique():
                sid_rows = am_df[am_df["seller_id"] == sid]
                if sid_rows.empty:
                    continue
                am_name = _normalize_am_name(sid_rows.iloc[0]["am_name"])
                df.loc[seller_mask & (df["vendor_id"] == sid), "pm_am"] = am_name

    return df


def load_data_from_db(
    start_date: date | None = None,
    end_date: date | None = None,
    warehouse: str = "All",
) -> pd.DataFrame:
    """
    Load inbound quality data from MySQL database.

    Parameters
    ----------
    start_date : date, optional
        Start of the evaluation window. Defaults to today - 180 days.
    end_date : date, optional
        End of the evaluation window. Defaults to today.
    warehouse : str
        Warehouse scope: "All", "LA", or "NJ". Affects which warehouse's
        cases are included in the aggregation.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns matching the Data Loader interface spec.
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=180)

    engine = _get_engine()

    # Load the three data components
    inbound_df = _load_inbound_volume(engine, start_date, end_date, warehouse)
    bpm_df = _load_bpm_data(engine, start_date, end_date, warehouse)
    qc_df = _load_qc_data(engine, start_date, end_date, warehouse)

    # Merge and compute rates
    df = _compute_rates(inbound_df, bpm_df, qc_df)

    # Load Seller responsiveness: avg days from BPM creation to edit (Seller only)
    wh_filter = _warehouse_filter_bpm(warehouse)
    resp_sql = f"""
    SELECT bpm.vendor_id,
           AVG(TIMESTAMPDIFF(HOUR, FROM_UNIXTIME(bpm.in_dtm), FROM_UNIXTIME(bpm.edit_dtm)) / 24.0) AS avg_days
    FROM yamibuy_wh.wh_problem_solving_bpm bpm
    WHERE bpm.business_type = 5
      AND bpm.create_type = 1
      AND bpm.edit_dtm > bpm.in_dtm
      AND bpm.in_dtm >= UNIX_TIMESTAMP('{start_date.isoformat()}')
      AND bpm.in_dtm < UNIX_TIMESTAMP('{end_date.isoformat()}')
      {wh_filter}
      AND bpm.vendor_id IS NOT NULL AND bpm.vendor_id != 0
    GROUP BY bpm.vendor_id
    """
    try:
        with engine.connect() as conn:
            resp_df = pd.read_sql(text(resp_sql), conn)
        if not resp_df.empty:
            resp_map = resp_df.set_index("vendor_id")["avg_days"]
            seller_mask = df["business_type"] == "Seller"
            df.loc[seller_mask, "responsiveness_days"] = (
                df.loc[seller_mask, "vendor_id"].map(resp_map).fillna(0)
            )
    except Exception:
        pass  # Keep default 0 if query fails

    # Select final output columns
    df = _select_output_columns(df)

    # Load owner (PM for Vendor, AM for Seller)
    try:
        df = _load_owner_info(engine, df)
    except Exception:
        df["pm_am"] = ""

    # Load active status (Vendor: po_vendor.status='A', Seller: xysc_vendor_info.is_active=1)
    df["is_active"] = False
    try:
        with engine.connect() as conn:
            # Vendor active status
            vendor_active = pd.read_sql(text(
                "SELECT vendor_id, (status = 'A') AS active FROM yamibuy_po.po_vendor"
            ), conn)
            vendor_mask = df["business_type"] == "Vendor"
            active_map = vendor_active.set_index("vendor_id")["active"]
            df.loc[vendor_mask, "is_active"] = (
                df.loc[vendor_mask, "vendor_id"].map(active_map).fillna(False).astype(bool)
            )

            # Seller active status
            seller_active = pd.read_sql(text(
                "SELECT vendor_id, (is_active = 1) AS active FROM yamibuy_master.xysc_vendor_info"
            ), conn)
            seller_mask = df["business_type"] == "Seller"
            active_map_s = seller_active.set_index("vendor_id")["active"]
            df.loc[seller_mask, "is_active"] = (
                df.loc[seller_mask, "vendor_id"].map(active_map_s).fillna(False).astype(bool)
            )
    except Exception:
        df["is_active"] = True  # Default to showing all if query fails

    # Ensure proper types
    df["vendor_id"] = df["vendor_id"].astype(int)
    df["qty_received"] = df["qty_received"].astype(int)
    df["business_type"] = df["business_type"].astype(str)

    return df


# ---------------------------------------------------------------------------
# CSV Validation and Main Entry Point
# ---------------------------------------------------------------------------


def validate_csv_columns(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """
    Validate that a DataFrame contains all required columns for the simulator.

    Checks the DataFrame's columns against REQUIRED_CSV_COLUMNS from config.py.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame parsed from a CSV upload.

    Returns
    -------
    tuple[bool, list[str]]
        A tuple of (is_valid, missing_columns) where:
        - is_valid is True if ALL required columns are present
        - missing_columns is a list of column names that are missing
          (empty list when is_valid is True)
    """
    existing_columns = set(df.columns)
    missing = [col for col in REQUIRED_CSV_COLUMNS if col not in existing_columns]
    is_valid = len(missing) == 0
    return is_valid, missing


def load_data(
    start_date: date | None = None,
    end_date: date | None = None,
    warehouse: str = "All",
    csv_file=None,
) -> pd.DataFrame:
    """
    Main entry point for loading inbound quality data.

    Parameters
    ----------
    start_date : date, optional
        Start of evaluation window. Defaults to today - 180 days.
    end_date : date, optional
        End of evaluation window. Defaults to today.
    warehouse : str
        Warehouse scope: "All", "LA", or "NJ".
    csv_file : file-like or Streamlit UploadedFile, optional
        A CSV file to parse.
    """
    if csv_file is not None:
        # Parse CSV from uploaded file
        df = pd.read_csv(csv_file)

        # Validate required columns
        is_valid, missing = validate_csv_columns(df)
        if not is_valid:
            raise ValueError(
                f"CSV file is missing required columns: {missing}"
            )

        # Ensure consistent types
        df["vendor_id"] = df["vendor_id"].astype(int)
        df["business_type"] = df["business_type"].astype(str)
        df["qty_received"] = df["qty_received"].astype(int)

        return df

    # No CSV provided — load from database
    df = load_data_from_db(start_date=start_date, end_date=end_date, warehouse=warehouse)
    return df


# ---------------------------------------------------------------------------
# Inactive Vendors/Sellers Query
# ---------------------------------------------------------------------------


def load_inactive_vendors(
    start_date: date | None = None,
    end_date: date | None = None,
    warehouse: str = "All",
) -> pd.DataFrame:
    """
    Load vendors/sellers that had PO activity in the past year but
    NO inbound receiving in the scoring window (start_date to end_date).

    Definition of "inactive":
    - Vendor: Has a po_purchase_order created in the past 12 months,
      but zero wh_inbound_batch records in the scoring window.
    - Seller: Has a wh_seller_shipment created in the past 12 months,
      but zero wh_inbound_batch records in the scoring window.

    Returns DataFrame with columns: vendor_id, vendor_name, business_type,
    last_po_date (most recent PO/shipment date).
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=180)

    # "Past year" = 12 months before end_date
    one_year_ago = end_date - timedelta(days=365)

    wh_filter_inbound = _warehouse_filter_inbound(warehouse)
    wh_filter_bpm = _warehouse_filter_bpm(warehouse)

    # Vendors with PO in past year but no inbound in scoring window
    vendor_sql = f"""
    SELECT pv.vendor_id, pv.vendor_name, 'Vendor' AS business_type,
           MAX(ppo.in_dtm) AS last_po_date
    FROM yamibuy_po.po_purchase_order ppo
    JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
    WHERE ppo.po_number NOT LIKE 'F%'
      AND ppo.in_dtm >= '{one_year_ago.isoformat()}'
      AND ppo.in_dtm < '{end_date.isoformat()}'
      AND pv.vendor_name IS NOT NULL
      AND pv.vendor_name NOT LIKE '%测试%'
      AND pv.vendor_id NOT IN (
          SELECT DISTINCT ppo2.vendor_id
          FROM yamibuy_wh.wh_inbound_batch ibb
          JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
          JOIN yamibuy_po.po_purchase_order ppo2 ON ppo2.po_number = ib.reference_id
          WHERE ib.reference_id NOT LIKE 'F%'
            AND ibb.item_number NOT LIKE '8%'
            AND ibb.in_dtm >= UNIX_TIMESTAMP('{start_date.isoformat()}')
            AND ibb.in_dtm < UNIX_TIMESTAMP('{end_date.isoformat()}')
            {wh_filter_inbound}
      )
    GROUP BY pv.vendor_id, pv.vendor_name
    """

    # Sellers with shipment in past year but no inbound in scoring window
    seller_sql = f"""
    SELECT wss.seller_id AS vendor_id, seller.vendor_name, 'Seller' AS business_type,
           MAX(wss.in_dtm) AS last_po_date
    FROM yamibuy_wh.wh_seller_shipment wss
    JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = wss.seller_id
    WHERE wss.in_dtm >= '{one_year_ago.isoformat()}'
      AND wss.in_dtm < '{end_date.isoformat()}'
      AND seller.vendor_name IS NOT NULL
      AND seller.vendor_name NOT LIKE '%测试%'
      AND wss.seller_id NOT IN (
          SELECT DISTINCT wss2.seller_id
          FROM yamibuy_wh.wh_inbound_batch ibb
          JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
          JOIN yamibuy_wh.wh_seller_shipment wss2 ON wss2.shipment_id = ib.reference_id
          WHERE ib.reference_id LIKE 'F%'
            AND ibb.in_dtm >= UNIX_TIMESTAMP('{start_date.isoformat()}')
            AND ibb.in_dtm < UNIX_TIMESTAMP('{end_date.isoformat()}')
            {wh_filter_inbound}
      )
    GROUP BY wss.seller_id, seller.vendor_name
    """

    engine = _get_engine()
    with engine.connect() as conn:
        vendor_df = pd.read_sql(text(vendor_sql), conn)
        seller_df = pd.read_sql(text(seller_sql), conn)

    df = pd.concat([vendor_df, seller_df], ignore_index=True)

    if not df.empty:
        df["vendor_id"] = df["vendor_id"].astype(int)
        df["last_po_date"] = pd.to_datetime(df["last_po_date"])

    return df
