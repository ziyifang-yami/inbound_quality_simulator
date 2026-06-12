"""
Exporter module for the Inbound Quality Score Simulator.

Provides CSV and Google Sheets export functionality for scored simulation results.
Exports include simulation parameters (weights, thresholds, tier boundaries) as metadata.
"""

import io
import json
import pandas as pd


def export_csv(
    df: pd.DataFrame,
    weights: dict,
    thresholds: dict,
    tier_boundaries: dict,
) -> bytes:
    """
    Export scored DataFrame to CSV bytes with a metadata header section.

    The CSV output begins with comment lines (prefixed with '#') containing
    simulation parameters as JSON, followed by standard CSV data rows.

    Args:
        df: Scored DataFrame with vendor/seller records.
        weights: Weight configuration dict (e.g., {'Vendor': {...}, 'Seller': {...}}).
        thresholds: Threshold configuration dict.
        tier_boundaries: Tier boundary dict (e.g., {'A': 95, 'B': 80, 'C': 60}).

    Returns:
        CSV content as bytes, suitable for Streamlit's download_button.
    """
    buffer = io.StringIO()

    # Write metadata header section as comment lines
    buffer.write("# === Simulation Parameters ===\n")
    buffer.write(f"# Tier Boundaries: {json.dumps(tier_boundaries)}\n")
    buffer.write(f"# Weights: {json.dumps(weights)}\n")
    buffer.write(f"# Thresholds: {json.dumps(thresholds)}\n")
    buffer.write("# === End Parameters ===\n")

    # Write the DataFrame as standard CSV
    df.to_csv(buffer, index=False)

    return buffer.getvalue().encode("utf-8")


def export_google_sheet(
    df: pd.DataFrame,
    weights: dict,
    thresholds: dict,
    tier_boundaries: dict,
    spreadsheet_name: str,
) -> str:
    """
    Create or update a Google Sheet with scored results and simulation parameters.

    Uses gspread with a service account for authentication. Creates a spreadsheet
    with two sheets:
      - "Parameters": Contains simulation metadata (weights, thresholds, boundaries).
      - "Results": Contains the scored data rows.

    Args:
        df: Scored DataFrame with vendor/seller records.
        weights: Weight configuration dict.
        thresholds: Threshold configuration dict.
        tier_boundaries: Tier boundary dict.
        spreadsheet_name: Name for the Google Sheets spreadsheet.

    Returns:
        The URL of the created/updated Google Sheet.

    Raises:
        FileNotFoundError: If the service account JSON file is not found.
        gspread.exceptions.APIError: If Google Sheets API call fails.
    """
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    import os

    # Authenticate with Google Sheets API via service account
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials_path = os.getenv(
        "GOOGLE_SHEETS_CREDENTIALS",
        "service_account.json",
    )
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
    client = gspread.authorize(creds)

    # Try to open existing spreadsheet, or create a new one
    try:
        spreadsheet = client.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create(spreadsheet_name)

    # --- Parameters sheet ---
    try:
        params_sheet = spreadsheet.worksheet("Parameters")
        params_sheet.clear()
    except gspread.WorksheetNotFound:
        params_sheet = spreadsheet.add_worksheet(
            title="Parameters", rows=50, cols=10
        )

    # Build parameters content
    params_data = [
        ["=== Simulation Parameters ==="],
        [""],
        ["Tier Boundaries"],
        ["Tier", "Min Score"],
    ]
    for tier, score in sorted(tier_boundaries.items()):
        params_data.append([f"Tier {tier}", str(score)])

    params_data.append([""])
    params_data.append(["Weights"])

    for btype, w in weights.items():
        params_data.append([f"--- {btype} ---"])
        params_data.append(["Criteria", "Weight (%)"])
        for criteria, value in w.items():
            params_data.append([criteria, str(value)])
        params_data.append([""])

    params_data.append(["Thresholds"])
    for btype, t in thresholds.items():
        params_data.append([f"--- {btype} ---"])
        params_data.append(["Criteria", "A", "B", "C"])
        for criteria, bounds in t.items():
            params_data.append([
                criteria,
                str(bounds.get("A", "")),
                str(bounds.get("B", "")),
                str(bounds.get("C", "")),
            ])
        params_data.append([""])

    params_sheet.update(range_name="A1", values=params_data)

    # --- Results sheet ---
    try:
        results_sheet = spreadsheet.worksheet("Results")
        results_sheet.clear()
    except gspread.WorksheetNotFound:
        results_sheet = spreadsheet.add_worksheet(
            title="Results", rows=max(len(df) + 1, 100), cols=len(df.columns) + 1
        )

    # Write header row + data rows
    header = df.columns.tolist()
    data_rows = df.astype(str).values.tolist()
    results_sheet.update(range_name="A1", values=[header] + data_rows)

    # Remove the default "Sheet1" if it exists and is empty
    try:
        default_sheet = spreadsheet.worksheet("Sheet1")
        if default_sheet.row_count <= 1 or default_sheet.get_all_values() == []:
            spreadsheet.del_worksheet(default_sheet)
    except (gspread.WorksheetNotFound, gspread.exceptions.APIError):
        pass

    return spreadsheet.url
