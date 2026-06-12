# Inbound Quality Score Simulator

Interactive Streamlit dashboard for evaluating and simulating vendor/seller inbound receiving quality performance at Yamibuy.

## Features

- **Scoring Engine** — Grades vendors/sellers across 10 criteria dimensions using configurable weights and thresholds
- **Tier Classification** — Assigns A/B/C/D tiers based on total weighted score
- **Interactive Simulation** — Adjust weights, thresholds, and tier boundaries in real-time to see impact on tier distribution
- **Impact Analysis** — Identifies tier upgrades/downgrades when parameters change vs baseline
- **Flexible Data Scope** — Filter by warehouse (LA/NJ/All), date range, business type, and team
- **Multiple Display Modes** — View scores, percentages, or actual case counts
- **Export** — Download results as CSV or push to Google Sheets

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up database credentials
cp .env.example .env
# Edit .env with your MySQL credentials

# Run the app
streamlit run app.py
```

Access at `http://localhost:8501`

## Data Sources

- **Database** — Connects to MySQL (rds.g3.yamibuy.net) and pulls 180 days of inbound quality metrics
- **CSV Upload** — Fallback option if database is unavailable

## Scoring Model

| Criteria | Vendor Weight | Seller Weight |
|----------|:---:|:---:|
| Overage | 15% | 10% |
| Damage | 15% | 15% |
| UPC/Label Error | 10% | 10% |
| Expiration Error | 15% | 15% |
| PO/Documentation | 5% | 10% |
| Wrong Items | 10% | 10% |
| Spec/Image Error | 5% | 15% |
| Packaging Error | 10% | 5% |
| Poor Quality | 15% | 5% |
| Responsiveness | 0% | 5% |

**Tier Boundaries (default):** A ≥ 95, B ≥ 80, C ≥ 60, D < 60

## Project Structure

```
simulator/
├── app.py              # Streamlit dashboard (main entry point)
├── config.py           # Default weights, thresholds, constants
├── scoring.py          # Grade computation + tier classification
├── validators.py       # Weight/threshold/boundary validation
├── data_loader.py      # MySQL queries + CSV fallback
├── impact.py           # Tier movement detection
├── exporter.py         # CSV + Google Sheets export
├── requirements.txt    # Python dependencies
├── .env.example        # Database credential template
└── test_*.py           # 122 tests (unit + property-based via Hypothesis)
```

## Running Tests

```bash
python -m pytest -v
```

## Tech Stack

- Python 3.11+
- Streamlit (web UI)
- Pandas + NumPy (computation)
- Plotly (charts)
- streamlit-aggrid (frozen column tables)
- SQLAlchemy + PyMySQL (database)
- Hypothesis (property-based testing)
