"""
Investigate unmatched records in each SQL to understand why and find better matches.
"""
import sys
sys.path.insert(0, '.')
from data_loader import _get_engine
from sqlalchemy import text

engine = _get_engine()

checks = [
    (
        "1. Seller BPM: unmatched reference_id samples (create_type=1, business_type=5)",
        """
        SELECT bpm.reference_id, bpm.issue_po_number, bpm.po_number, bpm.problem_type, bpm.item_qty
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = bpm.reference_id
        WHERE bpm.create_type = 1
          AND bpm.business_type = 5
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND wss.shipment_id IS NULL
        LIMIT 10
        """
    ),
    (
        "2. Seller QC: unmatched issue_po_number samples (create_type=2, business_type=5)",
        """
        SELECT bpm.issue_po_number, bpm.reference_id, bpm.po_number, bpm.comment, bpm.item_qty
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = bpm.issue_po_number
        WHERE bpm.create_type = 2
          AND bpm.business_type = 5
          AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND wss.shipment_id IS NULL
        LIMIT 10
        """
    ),
    (
        "3. Vendor QC: unmatched issue_po_number samples (create_type=2, business_type=1)",
        """
        SELECT bpm.issue_po_number, bpm.reference_id, bpm.po_number, bpm.item_qty
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_po.po_purchase_order ppo ON ppo.po_number = bpm.issue_po_number
        LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
        WHERE bpm.create_type = 2
          AND bpm.business_type = 1
          AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND pv.vendor_id IS NULL
        LIMIT 10
        """
    ),
    (
        "4. Check if unmatched Seller BPM reference_ids are old/deleted shipments",
        """
        SELECT bpm.reference_id,
               (SELECT COUNT(*) FROM yamibuy_wh.wh_seller_shipment WHERE shipment_id = bpm.reference_id) AS exists_in_shipment,
               (SELECT COUNT(*) FROM yamibuy_wh.wh_inbound WHERE reference_id = bpm.reference_id) AS exists_in_inbound
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = bpm.reference_id
        WHERE bpm.create_type = 1
          AND bpm.business_type = 5
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND wss.shipment_id IS NULL
          AND bpm.reference_id != ''
        LIMIT 5
        """
    ),
    (
        "5. Check if BPM has vendor_id directly (bypass JOIN entirely)",
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'yamibuy_wh'
          AND table_name = 'wh_problem_solving_bpm'
          AND column_name LIKE '%vendor%'
        """
    ),
    (
        "6. Check BPM table for seller_id or vendor_id columns",
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'yamibuy_wh'
          AND table_name = 'wh_problem_solving_bpm'
          AND (column_name LIKE '%seller%' OR column_name LIKE '%vendor%' OR column_name LIKE '%supplier%')
        """
    ),
]

print("=" * 60)
print("Investigating Unmatched Records")
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
                parts = [f"{col}={val!r}" for col, val in zip(cols, row)]
                print(f"    {', '.join(parts)}")
        except Exception as e:
            print(f"    ❌ ERROR: {e}")

print(f"\n{'=' * 60}")
print("Done.")
