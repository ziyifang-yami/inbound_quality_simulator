"""
Configuration constants for the Inbound Quality Score Simulator.

Contains default weights, thresholds, tier boundaries, and required CSV columns
for the vendor/seller quality scoring model.

Criteria mapping (from Google Sheet "Ops 入库质量 - Criteria Details"):
  1. damage        = 1.1 Inbound Defect Rate (Damage QTY / Received QTY)
  2. exp_error     = 1.2 Expiry/Shelf Life Issue Rate (EXP QTY / Received QTY)
  3. overage       = 1.3 Overage Issue Rate (Overage QTY / Received QTY)
  4. spec_image_error = 1.4 Spec/Pics Not Aligned Rate (Issues / TTL PO SKUs)
  5. no_data       = 1.5 Wrong Items Rate (Issued units / Received QTY)
  6. upc_error     = 1.6 Label/Barcode Inaccuracy Rate (Issued units / Received QTY)
  7. packaging_error = 2.1 Packaging Issue Rate (Issues / TTL PO SKUs)
  8. po_error      = 2.2 Documentation Inaccuracy Rate (Issued SKU / Received)
  9. responsiveness = 3.1 Responsiveness (Avg processed days)
  10. poor_quality  = 3.2 QC Random Check Issue Rate (Issued units / TTL PO units)
"""

# 10 quality criteria dimensions
CRITERIA_NAMES = [
    'damage', 'exp_error', 'overage', 'spec_image_error', 'no_data',
    'upc_error', 'packaging_error', 'po_error', 'responsiveness', 'poor_quality'
]

# Default weight configurations per business type (must sum to 100)
# Source: Google Sheet "Criteria Details" columns E-F
DEFAULT_WEIGHTS = {
    'Vendor': {
        'damage': 15,
        'exp_error': 15,
        'overage': 15,
        'spec_image_error': 5,
        'no_data': 10,
        'upc_error': 10,
        'packaging_error': 10,
        'po_error': 5,
        'responsiveness': 0,
        'poor_quality': 15,
    },
    'Seller': {
        'damage': 15,
        'exp_error': 15,
        'overage': 10,
        'spec_image_error': 15,
        'no_data': 10,
        'upc_error': 10,
        'packaging_error': 5,
        'po_error': 10,
        'responsiveness': 5,
        'poor_quality': 5,
    },
}

# Default grade boundary thresholds per business type
# For rate-based metrics: rate <= A → grade 100, A < rate <= B → 80, B < rate <= C → 60, rate > C → 20
# For responsiveness: days-based (lower is better, same logic)
# Values from Google Sheet "Criteria Details" — converted: percentage strings → decimal fractions
DEFAULT_THRESHOLDS = {
    'Vendor': {
        'damage':           {'A': 0.0001, 'B': 0.0005, 'C': 0.0025},   # <0.01%, 0.01-0.05%, 0.05-0.25%
        'exp_error':        {'A': 0.0001, 'B': 0.01,   'C': 0.05},     # <0.01%, 0.01-1%, 1-5%
        'overage':          {'A': 0.0001, 'B': 0.005,  'C': 0.02},     # <0.01%, 0.01-0.5%, 0.5-2%
        'spec_image_error': {'A': 0.0001, 'B': 0.03,   'C': 0.05},     # <0.01%, 0.01-3%, 3-5%
        'no_data':          {'A': 0.0001, 'B': 0.005,  'C': 0.05},     # <0.01%, 0.01-0.5%, 0.5-5%
        'upc_error':        {'A': 0.0001, 'B': 0.005,  'C': 0.05},     # <0.01%, 0.01-0.5%, 0.5-5%
        'packaging_error':  {'A': 0.0001, 'B': 0.005,  'C': 0.01},     # <0.01%, 0.01-0.5%, 0.5-1%
        'po_error':         {'A': 0.0001, 'B': 0.01,   'C': 0.05},     # <0.01%, 0.01-1%, 1-5%
        'responsiveness':   {'A': 1.5,    'B': 3,      'C': 7},        # <1.5 days, 1.5-3, 3-7
        'poor_quality':     {'A': 0.0001, 'B': 0.0005, 'C': 0.002},    # <0.01%, 0.01-0.05%, 0.05-0.2%
    },
    'Seller': {
        'damage':           {'A': 0.0001, 'B': 0.003,  'C': 0.015},    # <0.01%, 0.01-0.3%, 0.3-1.5%
        'exp_error':        {'A': 0.0001, 'B': 0.01,   'C': 0.05},     # <0.01%, 0.01-1%, 1-5%
        'overage':          {'A': 0.0001, 'B': 0.005,  'C': 0.02},     # <0.01%, 0.01-0.5%, 0.5-2%
        'spec_image_error': {'A': 0.0001, 'B': 0.03,   'C': 0.05},     # <0.01%, 0.01-3%, 3-5%
        'no_data':          {'A': 0.0001, 'B': 0.005,  'C': 0.05},     # <0.01%, 0.01-0.5%, 0.5-5%
        'upc_error':        {'A': 0.0001, 'B': 0.005,  'C': 0.05},     # <0.01%, 0.01-0.5%, 0.5-5%
        'packaging_error':  {'A': 0.0001, 'B': 0.005,  'C': 0.01},     # <0.01%, 0.01-0.5%, 0.5-1%
        'po_error':         {'A': 0.0001, 'B': 0.01,   'C': 0.05},     # <0.01%, 0.01-1%, 1-5%
        'responsiveness':   {'A': 1.5,    'B': 3,      'C': 7},        # <1.5 days, 1.5-3, 3-7
        'poor_quality':     {'A': 0.0001, 'B': 0.0005, 'C': 0.002},    # <0.01%, 0.01-0.05%, 0.05-0.2%
    },
}

# Tier classification boundaries (score >= boundary → assigned that tier)
# A > B > C; score < C → Tier D
DEFAULT_TIER_BOUNDARIES = {'A': 95, 'B': 80, 'C': 65}

# Required columns for CSV import validation
REQUIRED_CSV_COLUMNS = [
    'vendor_id',
    'vendor_name',
    'business_type',
    'qty_received',
    'damage_rate',
    'exp_error_rate',
    'overage_rate',
    'spec_image_error_rate',
    'no_data_rate',
    'upc_error_rate',
    'packaging_error_rate',
    'po_error_rate',
    'responsiveness_days',
    'poor_quality_rate',
]
