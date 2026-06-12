"""
Configuration constants for the Inbound Quality Score Simulator.

Contains default weights, thresholds, tier boundaries, and required CSV columns
for the vendor/seller quality scoring model.
"""

# 10 quality criteria dimensions
CRITERIA_NAMES = [
    'overage', 'damage', 'upc_error', 'exp_error', 'po_error',
    'no_data', 'spec_image_error', 'packaging_error', 'poor_quality', 'responsiveness'
]

# Default weight configurations per business type (must sum to 100)
DEFAULT_WEIGHTS = {
    'Vendor': {
        'overage': 15,
        'damage': 15,
        'upc_error': 10,
        'exp_error': 15,
        'po_error': 5,
        'no_data': 10,
        'spec_image_error': 5,
        'packaging_error': 10,
        'poor_quality': 15,
        'responsiveness': 0,
    },
    'Seller': {
        'overage': 10,
        'damage': 15,
        'upc_error': 10,
        'exp_error': 15,
        'po_error': 10,
        'no_data': 10,
        'spec_image_error': 15,
        'packaging_error': 5,
        'poor_quality': 5,
        'responsiveness': 5,
    },
}

# Default grade boundary thresholds per business type
# For rate-based metrics: rate <= A → grade 100, A < rate <= B → 80, B < rate <= C → 60, rate > C → 20
# For responsiveness: hours-based (lower is better, same logic)
DEFAULT_THRESHOLDS = {
    'Vendor': {
        'overage':          {'A': 0.005, 'B': 0.01,  'C': 0.03},
        'damage':           {'A': 0.005, 'B': 0.01,  'C': 0.02},
        'upc_error':        {'A': 0.00,  'B': 0.005, 'C': 0.01},
        'exp_error':        {'A': 0.005, 'B': 0.01,  'C': 0.03},
        'po_error':         {'A': 0.01,  'B': 0.03,  'C': 0.05},
        'no_data':          {'A': 0.005, 'B': 0.01,  'C': 0.03},
        'spec_image_error': {'A': 0.005, 'B': 0.01,  'C': 0.02},
        'packaging_error':  {'A': 0.005, 'B': 0.01,  'C': 0.03},
        'poor_quality':     {'A': 0.005, 'B': 0.01,  'C': 0.02},
        'responsiveness':   {'A': 24,    'B': 48,    'C': 72},
    },
    'Seller': {
        'overage':          {'A': 0.005, 'B': 0.01,  'C': 0.03},
        'damage':           {'A': 0.01,  'B': 0.02,  'C': 0.05},
        'upc_error':        {'A': 0.00,  'B': 0.005, 'C': 0.01},
        'exp_error':        {'A': 0.005, 'B': 0.01,  'C': 0.03},
        'po_error':         {'A': 0.01,  'B': 0.03,  'C': 0.05},
        'no_data':          {'A': 0.005, 'B': 0.01,  'C': 0.03},
        'spec_image_error': {'A': 0.01,  'B': 0.02,  'C': 0.05},
        'packaging_error':  {'A': 0.005, 'B': 0.01,  'C': 0.03},
        'poor_quality':     {'A': 0.005, 'B': 0.01,  'C': 0.02},
        'responsiveness':   {'A': 24,    'B': 48,    'C': 72},
    },
}

# Tier classification boundaries (score >= boundary → assigned that tier)
# A > B > C; score < C → Tier D
DEFAULT_TIER_BOUNDARIES = {'A': 95, 'B': 80, 'C': 60}

# Required columns for CSV import validation
REQUIRED_CSV_COLUMNS = [
    'warehouse_number',
    'vendor_id',
    'vendor_name',
    'business_type',
    'qty_received',
    'overage_rate',
    'damage_rate',
    'upc_error_rate',
    'exp_error_rate',
    'po_error_rate',
    'no_data_rate',
    'spec_image_error_rate',
    'packaging_error_rate',
    'poor_quality_rate',
    'responsiveness_hours',
]
