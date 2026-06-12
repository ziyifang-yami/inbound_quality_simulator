"""Check Seller QC BPM field values."""
import sys
sys.path.insert(0, '.')
from data_loader import _get_engine
from sqlalchemy import text

engine = _get_engine()

with engine.connect() as conn:
    print("=== Seller QC BPM fields (create_type=2, business_type=5, problem_type=3) ===")
    result = conn.execute(text("""
        SELECT bpm.reference_id, bpm.issue_po_number, bpm.po_number,
               bpm.comment, bpm.item_qty
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        WHERE bpm.create_type = 2
          AND bpm.business_type = 5
          AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
        LIMIT 10
    """))
    for row in result.fetchall():
        print(f"  ref={row[0]!r}, issue_po={row[1]!r}, po={row[2]!r}, comment={row[3]!r:.50}, qty={row[4]}")

    print("\n=== Try different JOIN keys for Seller QC ===")
    result2 = conn.execute(text("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN wss1.shipment_id IS NOT NULL THEN 1 ELSE 0 END) AS match_via_reference_id,
               SUM(CASE WHEN wss2.shipment_id IS NOT NULL THEN 1 ELSE 0 END) AS match_via_issue_po,
               SUM(CASE WHEN wss3.shipment_id IS NOT NULL THEN 1 ELSE 0 END) AS match_via_po_number
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss1 ON wss1.shipment_id = bpm.reference_id
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss2 ON wss2.shipment_id = bpm.issue_po_number
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss3 ON wss3.shipment_id = bpm.po_number
        WHERE bpm.create_type = 2
          AND bpm.business_type = 5
          AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
    """))
    for row in result2.fetchall():
        print(f"  total={row[0]}, match_ref={row[1]}, match_issue_po={row[2]}, match_po={row[3]}")
