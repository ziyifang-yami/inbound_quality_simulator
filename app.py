"""
Inbound Quality Score Simulator — Read-Only Demo Version.

Provides an interactive dashboard for viewing vendor/seller inbound quality
performance scores. All scoring parameters (weights, thresholds, tier boundaries)
are fixed to production defaults. Users can filter and explore results only.
"""

import os
from datetime import date, timedelta

import streamlit as st
import pandas as pd
import plotly.express as px

from config import (
    CRITERIA_NAMES,
    DEFAULT_WEIGHTS,
    DEFAULT_THRESHOLDS,
    DEFAULT_TIER_BOUNDARIES,
)
from scoring import compute_scores
from data_loader import load_data, load_inactive_vendors
from exporter import export_csv, export_google_sheet
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode


# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Inbound Quality Score Viewer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------


def _init_session_state():
    """Initialize session state with default values on first load."""
    if "scored_df" not in st.session_state:
        st.session_state.scored_df = None
    if "filters" not in st.session_state:
        st.session_state.filters = {
            "warehouse": "All",
            "business_type": "All",
            "team": "All",
        }
    if "data_source" not in st.session_state:
        st.session_state.data_source = "Database"


_init_session_state()


# ---------------------------------------------------------------------------
# Helper: Compute Scores (fixed parameters)
# ---------------------------------------------------------------------------


def _compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Compute scores with fixed production parameters."""
    return compute_scores(
        df,
        weights=DEFAULT_WEIGHTS,
        thresholds=DEFAULT_THRESHOLDS,
        tier_boundaries=DEFAULT_TIER_BOUNDARIES,
    )


# ---------------------------------------------------------------------------
# Sidebar: Data Source
# ---------------------------------------------------------------------------

st.sidebar.title("📊 Data Controls")

st.sidebar.header("Data Source")
data_source = st.sidebar.radio(
    "Select data source:",
    options=["Database", "CSV Upload"],
    index=0 if st.session_state.data_source == "Database" else 1,
    key="data_source_radio",
)
st.session_state.data_source = data_source

# Handle data loading
raw_df = None

if data_source == "CSV Upload":
    uploaded_file = st.sidebar.file_uploader(
        "Upload CSV file", type=["csv"], key="csv_uploader"
    )
    if uploaded_file is not None:
        try:
            raw_df = load_data(csv_file=uploaded_file)
            st.sidebar.success(f"✅ Loaded {len(raw_df)} records from CSV")
        except ValueError as e:
            st.sidebar.error(f"❌ {e}")
        except Exception as e:
            st.sidebar.error(f"❌ Failed to parse CSV: {e}")
else:
    # Database source — attempt to load on first run
    if st.session_state.scored_df is None:
        try:
            start_dt = st.session_state.get("date_start", date.today() - timedelta(days=180))
            end_dt = st.session_state.get("date_end", date.today())
            wh = st.session_state.filters.get("warehouse", "All")
            with st.spinner("Loading data from database..."):
                raw_df = load_data(start_date=start_dt, end_date=end_dt, warehouse=wh)
            st.sidebar.success(f"✅ Loaded {len(raw_df)} records from DB")
        except Exception as e:
            st.sidebar.warning(
                f"⚠️ Database connection failed: {e}\n\n"
                "Switch to CSV Upload to continue."
            )

# Compute scores on new data load
if raw_df is not None:
    st.session_state.scored_df = _compute_scores(raw_df)


# Human-readable display names for criteria
CRITERIA_DISPLAY = {
    "damage": "Defect/Damage",
    "exp_error": "Expiry/Shelf Life",
    "overage": "Overage",
    "spec_image_error": "Spec/Image",
    "no_data": "Wrong Items",
    "upc_error": "Label/Barcode",
    "packaging_error": "Packaging",
    "po_error": "Documentation",
    "responsiveness": "Responsiveness",
    "poor_quality": "QC Quality",
}


# ---------------------------------------------------------------------------
# Helper: Apply Filters to DataFrame
# ---------------------------------------------------------------------------


def _apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Apply current session state filters to the DataFrame."""
    filtered = df.copy()
    filters = st.session_state.filters

    if filters["business_type"] != "All":
        filtered = filtered[filtered["business_type"] == filters["business_type"]]
    if filters["team"] != "All":
        filtered = filtered[filtered["team"] == filters["team"]]

    return filtered


# ---------------------------------------------------------------------------
# Main Area: Title and Tabs
# ---------------------------------------------------------------------------

st.title("📊 Inbound Quality Dashboard")

if st.session_state.scored_df is None:
    st.info(
        "👈 Please load data using the sidebar controls to begin.\n\n"
        "Select **Database** to load from MySQL, or **CSV Upload** to import a file."
    )
else:
    # -----------------------------------------------------------------------
    # Filter Controls (above tabs, affect all views)
    # -----------------------------------------------------------------------

    filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns([1, 1, 1, 1, 1])

    with filter_col1:
        warehouse_options = ["All", "LA", "NJ"]
        wh_index = warehouse_options.index(st.session_state.filters["warehouse"])
        selected_wh = st.selectbox(
            "Warehouse",
            options=warehouse_options,
            index=wh_index,
            key="filter_warehouse",
        )

    with filter_col2:
        btype_options = ["All", "Vendor", "Seller"]
        bt_index = btype_options.index(st.session_state.filters["business_type"])
        selected_bt = st.selectbox(
            "Business Type",
            options=btype_options,
            index=bt_index,
            key="filter_business_type",
        )
        st.session_state.filters["business_type"] = selected_bt

    with filter_col3:
        team_options = ["All", "Food", "Non-food"]
        tm_index = team_options.index(st.session_state.filters["team"])
        selected_tm = st.selectbox(
            "Team",
            options=team_options,
            index=tm_index,
            key="filter_team",
        )
        st.session_state.filters["team"] = selected_tm

    with filter_col4:
        default_start = date.today() - timedelta(days=180)
        selected_start = st.date_input(
            "Start Date",
            value=st.session_state.get("date_start", default_start),
            key="filter_date_start",
        )

    with filter_col5:
        default_end = date.today()
        selected_end = st.date_input(
            "End Date",
            value=st.session_state.get("date_end", default_end),
            key="filter_date_end",
        )

    # --- Reload data from DB if warehouse or dates changed ---
    prev_start = st.session_state.get("date_start", default_start)
    prev_end = st.session_state.get("date_end", default_end)
    prev_wh = st.session_state.filters.get("warehouse", "All")

    need_reload = (
        (selected_start != prev_start or selected_end != prev_end or selected_wh != prev_wh)
        and data_source == "Database"
    )

    st.session_state.filters["warehouse"] = selected_wh
    st.session_state["date_start"] = selected_start
    st.session_state["date_end"] = selected_end

    if need_reload:
        try:
            with st.spinner("Reloading data for new parameters..."):
                raw_df = load_data(
                    start_date=selected_start,
                    end_date=selected_end,
                    warehouse=selected_wh,
                )
            st.session_state.scored_df = _compute_scores(raw_df)
            st.toast(f"✅ Reloaded {len(raw_df)} records ({selected_wh}, {selected_start} → {selected_end})")
        except Exception as e:
            st.warning(f"⚠️ Failed to reload: {e}")

    # Apply filters to scored data
    filtered_df = _apply_filters(st.session_state.scored_df)

    # Create tabs for the main dashboard
    tab_overview, tab_detail, tab_comparison, tab_inactive, tab_export = st.tabs(
        ["Overview", "Detail", "Comparison", "Inactive", "Export"]
    )

    # -------------------------------------------------------------------
    # Tab: Overview — Tier distribution chart + summary stats
    # -------------------------------------------------------------------
    with tab_overview:
        st.header("Tier Distribution Overview")

        if filtered_df.empty:
            st.info("No records match the current filter criteria.")
        else:
            # Summary statistics
            stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

            avg_score = filtered_df["total_score"].mean()
            total_records = len(filtered_df)
            tier_counts = filtered_df["tier"].value_counts()

            with stat_col1:
                st.metric("Total Records", total_records)
            with stat_col2:
                st.metric("Average Score", f"{avg_score:.1f}")
            with stat_col3:
                tier_a_count = tier_counts.get("A", 0)
                tier_b_count = tier_counts.get("B", 0)
                st.metric("Tier A / B", f"{tier_a_count} / {tier_b_count}")
            with stat_col4:
                tier_c_count = tier_counts.get("C", 0)
                tier_d_count = tier_counts.get("D", 0)
                st.metric("Tier C / D", f"{tier_c_count} / {tier_d_count}")

            # Tier distribution charts side by side
            chart_col1, chart_col2 = st.columns(2)

            # Prepare tier distribution data with consistent ordering
            tier_order = ["A", "B", "C", "D"]
            tier_dist = (
                filtered_df["tier"]
                .value_counts()
                .reindex(tier_order, fill_value=0)
                .reset_index()
            )
            tier_dist.columns = ["Tier", "Count"]
            tier_dist["Percentage"] = (
                tier_dist["Count"] / tier_dist["Count"].sum() * 100
            ).round(1)

            tier_colors = {"A": "#2ecc71", "B": "#3498db", "C": "#f39c12", "D": "#e74c3c"}

            with chart_col1:
                fig_pie = px.pie(
                    tier_dist,
                    values="Count",
                    names="Tier",
                    title="Tier Distribution (Pie)",
                    color="Tier",
                    color_discrete_map=tier_colors,
                    hole=0.3,
                )
                fig_pie.update_traces(textinfo="label+percent+value")
                st.plotly_chart(fig_pie, use_container_width=True)

            with chart_col2:
                fig_bar = px.bar(
                    tier_dist,
                    x="Tier",
                    y="Count",
                    title="Tier Distribution (Bar)",
                    color="Tier",
                    color_discrete_map=tier_colors,
                    text="Count",
                )
                fig_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)

            # Detailed tier count table
            st.subheader("Tier Summary")
            summary_data = []
            for tier in tier_order:
                tier_subset = filtered_df[filtered_df["tier"] == tier]
                count = len(tier_subset)
                pct = (count / total_records * 100) if total_records > 0 else 0
                avg = tier_subset["total_score"].mean() if count > 0 else 0
                summary_data.append({
                    "Tier": tier,
                    "Count": count,
                    "Percentage": f"{pct:.1f}%",
                    "Avg Score": f"{avg:.1f}",
                })
            st.dataframe(
                pd.DataFrame(summary_data),
                use_container_width=True,
                hide_index=True,
            )

    # -------------------------------------------------------------------
    # Tab: Detail — Full results table with display mode toggle
    # -------------------------------------------------------------------
    with tab_detail:
        st.header("Detail Table")

        if filtered_df.empty:
            st.info("No records match the current filter criteria.")
        else:
            # Search bars and display mode on the same row
            search_id_col, search_name_col, search_pm_col, mode_col = st.columns([1, 2, 1.5, 3])
            with search_id_col:
                search_id = st.text_input(
                    "Vendor/Seller ID",
                    placeholder="Exact ID...",
                    key="detail_search_id",
                )
            with search_name_col:
                search_name = st.text_input(
                    "Vendor/Seller Name",
                    placeholder="Partial name...",
                    key="detail_search_name",
                )
            with search_pm_col:
                # Build PM/AM dropdown from available data
                pm_am_options = ["All"] + sorted(
                    filtered_df["pm_am"].dropna().loc[filtered_df["pm_am"] != ""].unique().tolist()
                )
                selected_pm = st.selectbox(
                    "PM/AM",
                    options=pm_am_options,
                    index=0,
                    key="detail_filter_pm_am",
                )
            with mode_col:
                st.write("")  # spacing to align
                st.write("")  # extra spacing
                display_mode = st.radio(
                    "mode",
                    options=["Score", "Percentage", "Actual Cases"],
                    horizontal=True,
                    key="detail_display_mode",
                    label_visibility="collapsed",
                )

            # Apply search filters
            display_filtered_df = filtered_df.copy()
            if search_id:
                display_filtered_df = display_filtered_df[
                    display_filtered_df["vendor_id"].astype(str) == search_id.strip()
                ]
            if search_name:
                display_filtered_df = display_filtered_df[
                    display_filtered_df["vendor_name"].str.contains(search_name, case=False, na=False)
                ]
            if selected_pm != "All":
                display_filtered_df = display_filtered_df[
                    display_filtered_df["pm_am"] == selected_pm
                ]

            st.caption(f"Showing {len(display_filtered_df)} records. Click column headers to sort.")

            # Base columns: Tier and Total Score first, then identifiers
            base_cols = [
                "tier",
                "total_score",
                "vendor_name",
                "vendor_id",
                "business_type",
                "team",
                "pm_am",
            ]

            # Build rename map for base columns
            rename_map = {
                "business_type": "Type",
                "team": "Team",
                "vendor_id": "ID",
                "vendor_name": "Name",
                "qty_received": "Qty Received (units)",
                "total_score": "Score",
                "tier": "Tier",
                "pm_am": "PM/AM",
            }

            if display_mode == "Score":
                # Show grade columns (100/80/60/20)
                criteria_cols = [f"grade_{c}" for c in CRITERIA_NAMES]
                for criteria in CRITERIA_NAMES:
                    col_name = f"grade_{criteria}"
                    display_name = CRITERIA_DISPLAY.get(criteria, criteria)
                    rename_map[col_name] = f"{display_name} (score)"

            elif display_mode == "Percentage":
                # Show rate columns as percentages
                criteria_cols = []
                for criteria in CRITERIA_NAMES:
                    if criteria == "responsiveness":
                        criteria_cols.append("responsiveness_days")
                        rename_map["responsiveness_days"] = "Responsiveness (days)"
                    else:
                        col = f"{criteria}_rate"
                        criteria_cols.append(col)
                        display_name = CRITERIA_DISPLAY.get(criteria, criteria)
                        rename_map[col] = f"{display_name} (%)"

            else:  # Actual Cases
                # Show raw numerator quantities + qty_received as context
                criteria_cols = ["qty_received"]
                qty_col_map = {
                    "overage": "overage_qty",
                    "damage": "damage_qty",
                    "upc_error": "upc_qty",
                    "exp_error": "exp_qty",
                    "po_error": "po_qty",
                    "no_data": "no_data_qty",
                    "spec_image_error": "spec_image_error",
                    "packaging_error": "packaging_error",
                    "poor_quality": "poor_quality_qty",
                    "responsiveness": "responsiveness_days",
                }
                for criteria in CRITERIA_NAMES:
                    col = qty_col_map[criteria]
                    criteria_cols.append(col)
                    display_name = CRITERIA_DISPLAY.get(criteria, criteria)
                    if criteria == "responsiveness":
                        rename_map[col] = "Responsiveness (days)"
                    else:
                        rename_map[col] = f"{display_name} (qty)"

            # Assemble display columns
            display_cols = base_cols + criteria_cols

            # Filter to only columns that exist
            available_cols = [c for c in display_cols if c in display_filtered_df.columns]
            detail_df = display_filtered_df[available_cols].copy()

            # For Percentage mode, convert rates to percentage display
            if display_mode == "Percentage":
                for criteria in CRITERIA_NAMES:
                    if criteria != "responsiveness":
                        col = f"{criteria}_rate"
                        if col in detail_df.columns:
                            detail_df[col] = (detail_df[col] * 100).round(2)

            detail_df = detail_df.rename(columns=rename_map)

            # Sort by Tier (A first) then Score descending
            if "Tier" in detail_df.columns and "Score" in detail_df.columns:
                tier_order_map = {"A": 0, "B": 1, "C": 2, "D": 3}
                detail_df["_tier_rank"] = detail_df["Tier"].map(tier_order_map)
                detail_df = detail_df.sort_values(
                    ["_tier_rank", "Score"], ascending=[True, False]
                ).drop(columns=["_tier_rank"])

            # Determine number of pinned (frozen) columns based on display mode
            if display_mode == "Actual Cases":
                num_pinned = 8
            else:
                num_pinned = 7

            # Use AgGrid for frozen (pinned) left columns
            gb = GridOptionsBuilder.from_dataframe(detail_df)
            gb.configure_default_column(sortable=True, resizable=True, filterable=False, width=100)

            # Pin the first N columns to the left with compact widths
            col_widths = {
                "Tier": 45,
                "Score": 65,
                "Name": 180,
                "ID": 60,
                "Type": 70,
                "Team": 80,
                "PM/AM": 130,
                "Qty Received (units)": 110,
            }
            for i, col in enumerate(detail_df.columns[:num_pinned]):
                w = col_widths.get(col, 100)
                gb.configure_column(col, pinned="left", width=w)

            # Right-align numeric data columns (criteria scores/percentages/quantities)
            for col in detail_df.columns[num_pinned:]:
                gb.configure_column(col, type=["numericColumn"], cellStyle={"textAlign": "right"})

            # Set compact row height
            gb.configure_grid_options(domLayout="normal", rowHeight=30, headerHeight=32)
            grid_options = gb.build()

            AgGrid(
                detail_df,
                gridOptions=grid_options,
                height=600,
                fit_columns_on_grid_load=False,
                update_mode=GridUpdateMode.NO_UPDATE,
                theme="streamlit",
            )

    # -------------------------------------------------------------------
    # Tab: Comparison — Vendor vs Seller, Food vs Non-food
    # -------------------------------------------------------------------
    with tab_comparison:
        st.header("Comparison View")

        df = st.session_state.scored_df

        # --- Helper: build tier distribution figure ---
        def _tier_distribution_chart(subset: pd.DataFrame, title: str):
            """Return a Plotly bar chart of tier distribution for a subset."""
            if subset.empty:
                return None
            tier_counts = (
                subset["tier"]
                .value_counts()
                .reindex(["A", "B", "C", "D"], fill_value=0)
                .reset_index()
            )
            tier_counts.columns = ["Tier", "Count"]
            fig = px.bar(
                tier_counts,
                x="Tier",
                y="Count",
                color="Tier",
                color_discrete_map={"A": "#2ecc71", "B": "#3498db", "C": "#f39c12", "D": "#e74c3c"},
                title=title,
                text="Count",
            )
            fig.update_layout(showlegend=False, height=350, margin=dict(t=40))
            fig.update_traces(textposition="outside")
            return fig

        # --- Helper: segment summary stats ---
        def _segment_summary(subset: pd.DataFrame, label: str) -> dict:
            """Return summary dict for a segment."""
            if subset.empty:
                return {
                    "Segment": label,
                    "Records": 0,
                    "Avg Score": 0.0,
                    "Tier A": 0,
                    "Tier B": 0,
                    "Tier C": 0,
                    "Tier D": 0,
                }
            tier_counts = subset["tier"].value_counts()
            return {
                "Segment": label,
                "Records": len(subset),
                "Avg Score": round(subset["total_score"].mean(), 2),
                "Tier A": int(tier_counts.get("A", 0)),
                "Tier B": int(tier_counts.get("B", 0)),
                "Tier C": int(tier_counts.get("C", 0)),
                "Tier D": int(tier_counts.get("D", 0)),
            }

        # Vendor vs Seller
        st.subheader("🤝 Vendor vs Seller Tier Distribution")

        df_vendor = df[df["business_type"] == "Vendor"]
        df_seller = df[df["business_type"] == "Seller"]

        col_v, col_s = st.columns(2)
        with col_v:
            fig_v = _tier_distribution_chart(df_vendor, "Vendor")
            if fig_v:
                st.plotly_chart(fig_v, use_container_width=True)
            else:
                st.info("No Vendor records.")
        with col_s:
            fig_s = _tier_distribution_chart(df_seller, "Seller")
            if fig_s:
                st.plotly_chart(fig_s, use_container_width=True)
            else:
                st.info("No Seller records.")

        # Food vs Non-food
        st.divider()
        st.subheader("🍎 Food vs 💄 Non-food (Vendor)")

        if "team" in df.columns:
            df_food = df_vendor[df_vendor["team"] == "Food"]
            df_nonfood = df_vendor[df_vendor["team"] == "Non-food"]

            col_f, col_nf = st.columns(2)
            with col_f:
                fig_food = _tier_distribution_chart(df_food, "Food")
                if fig_food:
                    st.plotly_chart(fig_food, use_container_width=True)
                else:
                    st.info("No Food records.")
            with col_nf:
                fig_nonfood = _tier_distribution_chart(df_nonfood, "Non-food")
                if fig_nonfood:
                    st.plotly_chart(fig_nonfood, use_container_width=True)
                else:
                    st.info("No Non-food records.")
        else:
            st.info("Team column not available in dataset.")

        # Segment-Level Summary
        st.divider()
        st.subheader("📊 Segment-Level Summary Statistics")

        summary_rows = [
            _segment_summary(df_vendor, "Vendor"),
            _segment_summary(df_seller, "Seller"),
        ]

        if "team" in df.columns:
            summary_rows.append(_segment_summary(df_food, "Food (Vendor)"))
            summary_rows.append(_segment_summary(df_nonfood, "Non-food (Vendor)"))

        summary_df = pd.DataFrame(summary_rows)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

    # -------------------------------------------------------------------
    # Tab: Inactive — Vendors with no recent inbound
    # -------------------------------------------------------------------
    with tab_inactive:
        st.header("Inactive Vendors/Sellers")
        st.caption(
            "**Definition:** Had PO/shipment activity in the past 12 months, "
            "but **zero inbound receiving** during the current scoring window. "
            "These vendors/sellers are not included in tier scoring."
        )

        try:
            inactive_df = load_inactive_vendors(
                start_date=st.session_state.get("date_start"),
                end_date=st.session_state.get("date_end"),
                warehouse=st.session_state.filters.get("warehouse", "All"),
            )

            if inactive_df.empty:
                st.info("No inactive vendors/sellers found for the current parameters.")
            else:
                vendor_count = len(inactive_df[inactive_df["business_type"] == "Vendor"])
                seller_count = len(inactive_df[inactive_df["business_type"] == "Seller"])

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Inactive", len(inactive_df))
                with col2:
                    st.metric("Vendors", vendor_count)
                with col3:
                    st.metric("Sellers", seller_count)

                btype_filter = st.radio(
                    "Show:",
                    options=["All", "Vendor", "Seller"],
                    horizontal=True,
                    key="inactive_btype_filter",
                )

                display_inactive = inactive_df.copy()
                if btype_filter != "All":
                    display_inactive = display_inactive[
                        display_inactive["business_type"] == btype_filter
                    ]

                display_inactive = display_inactive.rename(columns={
                    "vendor_id": "ID",
                    "vendor_name": "Name",
                    "business_type": "Type",
                    "last_po_date": "Last PO/Shipment Date",
                })

                display_inactive = display_inactive.sort_values(
                    "Last PO/Shipment Date", ascending=False
                )

                st.dataframe(
                    display_inactive,
                    use_container_width=True,
                    hide_index=True,
                    height=500,
                )

        except Exception as e:
            st.error(f"Failed to load inactive data: {e}")

    # -------------------------------------------------------------------
    # Tab: Export — CSV and Google Sheets
    # -------------------------------------------------------------------
    with tab_export:
        st.header("Export")

        current_df = st.session_state.scored_df

        # --- CSV Export ---
        st.subheader("📥 CSV Download")
        csv_bytes = export_csv(current_df, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, DEFAULT_TIER_BOUNDARIES)
        st.download_button(
            label="⬇️ Download CSV",
            data=csv_bytes,
            file_name="simulation_results.csv",
            mime="text/csv",
        )

        st.divider()

        # --- Google Sheets Export ---
        st.subheader("📊 Google Sheets Export")
        spreadsheet_name = st.text_input(
            "Spreadsheet name",
            value="Inbound Quality Score Results",
            key="export_sheet_name",
        )

        if st.button("🚀 Export to Google Sheets", key="export_gsheet_btn"):
            try:
                with st.spinner("Exporting to Google Sheets..."):
                    sheet_url = export_google_sheet(
                        current_df,
                        DEFAULT_WEIGHTS,
                        DEFAULT_THRESHOLDS,
                        DEFAULT_TIER_BOUNDARIES,
                        spreadsheet_name,
                    )
                st.success(f"✅ Export successful! [Open spreadsheet]({sheet_url})")
            except Exception as e:
                st.error(f"❌ Google Sheets export failed: {e}")
