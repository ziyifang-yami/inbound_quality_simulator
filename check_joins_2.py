"""
Validation script part 2: Seller Inbound + Vendor BPM + Seller BPM + QC
Run: python check_joins_2.py
"""
import sys
sys.path.insert(0, '.')

from data_loader import _get_engine
from sqlalchemy import text

engine = _get_engine()

checks = [
    (
        "1. Seller: wh_inbound → wh_seller_shipment (FBY JOIN match)",
        """
        SELECT COUNT(*) AS total_fby_inbound,
               SUM(CASE WHEN wss.shipment_id IS NULL THEN 1 ELSE 0 END) AS no_shipment_match
        FROM yamibuy_wh.wh_inbound ib
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = ib.reference_id
        WHERE ib.reference_id LIKE 'F%'
          AND ib.inbound_number IN (
            SELECT DISTINCT inbound_number FROM yamibuy_wh.wh_inbound_batch
            WHERE in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
          )
        """
    ),
    (
        "2. Seller: wh_seller_shipment → xysc_vendor_info (seller name match)",
        """
        SELECT COUNT(*) AS total_shipments,
               SUM(CASE WHEN seller.vendor_name IS NULL THEN 1 ELSE 0 END) AS no_name_match
        FROM yamibuy_wh.wh_seller_shipment wss
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = wss.seller_id
        WHERE wss.shipment_id IN (
            SELECT DISTINCT reference_id FROM yamibuy_wh.wh_inbound
            WHERE reference_id LIKE 'F%'
              AND inbound_number IN (
                SELECT DISTINCT inbound_number FROM yamibuy_wh.wh_inbound_batch
                WHERE in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
              )
        )
        """
    ),
    (
        "3. Vendor BPM: sample 5 rows (problem_type distribution)",
        """
        SELECT bpm.problem_type, COUNT(*) AS cnt, SUM(bpm.item_qty) AS total_qty
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        WHERE bpm.create_type = 1
          AND bpm.business_type = 1
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
        GROUP BY bpm.problem_type
        ORDER BY bpm.problem_type
        """
    ),
    (
        "4. Vendor BPM → PO → Vendor JOIN (match rate)",
        """
        SELECT COUNT(*) AS total_bpm,
               SUM(CASE WHEN pv.vendor_id IS NULL THEN 1 ELSE 0 END) AS no_vendor_match
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_po.po_purchase_order ppo
            ON ppo.po_number = (CASE WHEN bpm.reference_id != '' THEN bpm.reference_id ELSE bpm.po_number END)
        LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
        WHERE bpm.create_type = 1
          AND bpm.business_type = 1
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
        """
    ),
    (
        "5. Seller BPM → wh_seller_shipment → xysc_vendor_info (match rate)",
        """
        SELECT COUNT(*) AS total_bpm,
               SUM(CASE WHEN seller.vendor_id IS NULL THEN 1 ELSE 0 END) AS no_seller_match
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = bpm.issue_po_number
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = wss.seller_id
        WHERE bpm.create_type = 1
          AND bpm.business_type = 5
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
        """
    ),
    (
        "6. Vendor QC: create_type=2, problem_type=3, comment LIKE '%quality%'",
        """
        SELECT COUNT(*) AS total_qc_rows,
               SUM(bpm.item_qty) AS total_qty,
               SUM(CASE WHEN bpm.comment LIKE '%quality%' THEN bpm.item_qty ELSE 0 END) AS quality_qty
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        WHERE bpm.create_type = 2
          AND bpm.problem_type = 3
          AND bpm.business_type = 1
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
        """
    ),
    (
        "7. Seller QC: create_type=2, problem_type=3, comment LIKE '%quality%'",
        """
        SELECT COUNT(*) AS total_qc_rows,
               SUM(bpm.item_qty) AS total_qty,
               SUM(CASE WHEN bpm.comment LIKE '%quality%' THEN bpm.item_qty ELSE 0 END) AS quality_qty
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        WHERE bpm.create_type = 2
          AND bpm.problem_type = 3
          AND bpm.business_type = 5
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
        """
    ),
]

print("=" * 60)
print("SQL JOIN Validation Part 2: Seller + BPM + QC")
print("=" * 60)

with engine.connect() as conn:
    for title, sql in checks:
        print(f"\n{'─' * 60}")
        print(f"  {title}")
        print(f"{'─' * 60}")
        try:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            cols = result.keys()
            for row in rows:
                for col, val in zip(cols, row):
                    print(f"    {col}: {val}")
                if len(rows) > 1:
                    print()
        except Exception as e:
            print(f"    ❌ ERROR: {e}")

print(f"\n{'=' * 60}")
print("Done.")
