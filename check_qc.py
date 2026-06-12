"""
Validation script: QC Random Check SQL (Vendor + Seller)
Criteria 9: create_type=2, problem_type=3, comment LIKE '%quality%'
"""
import sys
sys.path.insert(0, '.')

from data_loader import _get_engine
from sqlalchemy import text

engine = _get_engine()

checks = [
    (
        "1. Vendor QC: JOIN match rate (bpm → po → vendor)",
        """
        SELECT COUNT(*) AS total_qc_bpm,
               SUM(CASE WHEN pv.vendor_id IS NULL THEN 1 ELSE 0 END) AS no_vendor_match
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_po.po_purchase_order ppo ON ppo.po_number = bpm.issue_po_number
        LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
        WHERE bpm.create_type = 2
          AND bpm.business_type = 1
          AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
        """
    ),
    (
        "2. Vendor QC: sample rows with comment field",
        """
        SELECT bpm.issue_po_number, bpm.reference_id, bpm.comment, bpm.item_qty,
               pv.vendor_id, pv.vendor_name
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_po.po_purchase_order ppo ON ppo.po_number = bpm.issue_po_number
        LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
        WHERE bpm.create_type = 2
          AND bpm.business_type = 1
          AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
          AND bpm.comment LIKE '%quality%'
          AND pv.vendor_name IS NOT NULL
        LIMIT 5
        """
    ),
    (
        "3. Vendor QC: total quality qty by top vendors",
        """
        SELECT pv.vendor_id, pv.vendor_name,
               SUM(CASE WHEN bpm.comment LIKE '%quality%' THEN bpm.item_qty ELSE 0 END) AS poor_quality_qty,
               COUNT(*) AS total_rows
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_po.po_purchase_order ppo ON ppo.po_number = bpm.issue_po_number
        LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
        WHERE bpm.create_type = 2
          AND bpm.business_type = 1
          AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND pv.vendor_name IS NOT NULL
          AND pv.vendor_name NOT LIKE '%测试%'
        GROUP BY pv.vendor_id, pv.vendor_name
        ORDER BY poor_quality_qty DESC
        LIMIT 5
        """
    ),
    (
        "4. Seller QC: JOIN match rate (bpm → seller_shipment via reference_id)",
        """
        SELECT COUNT(*) AS total_qc_bpm,
               SUM(CASE WHEN seller.vendor_id IS NULL THEN 1 ELSE 0 END) AS no_seller_match
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = bpm.reference_id
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = wss.seller_id
        WHERE bpm.create_type = 2
          AND bpm.business_type = 5
          AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
        """
    ),
    (
        "5. Seller QC: sample rows with comment",
        """
        SELECT bpm.reference_id, bpm.issue_po_number, bpm.comment, bpm.item_qty,
               wss.seller_id, seller.vendor_name
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = bpm.reference_id
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = wss.seller_id
        WHERE bpm.create_type = 2
          AND bpm.business_type = 5
          AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
          AND bpm.comment LIKE '%quality%'
          AND seller.vendor_name IS NOT NULL
        LIMIT 5
        """
    ),
    (
        "6. Seller QC: total quality qty by top sellers",
        """
        SELECT wss.seller_id AS vendor_id, seller.vendor_name,
               SUM(CASE WHEN bpm.comment LIKE '%quality%' THEN bpm.item_qty ELSE 0 END) AS poor_quality_qty,
               COUNT(*) AS total_rows
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = bpm.reference_id
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = wss.seller_id
        WHERE bpm.create_type = 2
          AND bpm.business_type = 5
          AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND seller.vendor_name IS NOT NULL
          AND seller.vendor_name NOT LIKE '%测试%'
        GROUP BY wss.seller_id, seller.vendor_name
        ORDER BY poor_quality_qty DESC
        LIMIT 5
        """
    ),
]

print("=" * 60)
print("QC Random Check SQL Validation")
print("=" * 60)

with engine.connect() as conn:
    for title, sql in checks:
        print(f"\n{'─' * 60}")
        print(f"  {title}")
        print(f"{'─' * 60}")
        try:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            cols = list(result.keys())
            if not rows:
                print("    (no rows)")
            for row in rows:
                parts = [f"{col}={val}" for col, val in zip(cols, row)]
                print(f"    {', '.join(parts)}")
        except Exception as e:
            print(f"    ❌ ERROR: {e}")

print(f"\n{'=' * 60}")
print("Done.")
