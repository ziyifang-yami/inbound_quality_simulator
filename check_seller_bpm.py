"""Check Seller BPM field values to find correct JOIN key."""
import sys
sys.path.insert(0, '.')
from data_loader import _get_engine
from sqlalchemy import text

engine = _get_engine()

with engine.connect() as conn:
    # Check what fields Seller BPM has for linking to shipments
    print("=== Seller BPM sample (business_type=5, create_type=1) ===")
    result = conn.execute(text("""
        SELECT bpm.issue_po_number, bpm.reference_id, bpm.po_number,
               bpm.problem_type, bpm.item_qty
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        WHERE bpm.create_type = 1
          AND bpm.business_type = 5
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
        LIMIT 10
    """))
    for row in result.fetchall():
        print(f"  issue_po_number={row[0]!r}, reference_id={row[1]!r}, po_number={row[2]!r}, type={row[3]}, qty={row[4]}")

    # Check what wh_seller_shipment.shipment_id looks like
    print("\n=== wh_seller_shipment sample (recent) ===")
    result2 = conn.execute(text("""
        SELECT wss.shipment_id, wss.seller_id
        FROM yamibuy_wh.wh_seller_shipment wss
        ORDER BY wss.shipment_id DESC
        LIMIT 5
    """))
    for row in result2.fetchall():
        print(f"  shipment_id={row[0]!r}, seller_id={row[1]}")

    # Try matching on reference_id instead of issue_po_number
    print("\n=== Try JOIN on reference_id instead ===")
    result3 = conn.execute(text("""
        SELECT COUNT(*) AS total_bpm,
               SUM(CASE WHEN wss.shipment_id IS NULL THEN 1 ELSE 0 END) AS no_match_ref,
               SUM(CASE WHEN wss2.shipment_id IS NULL THEN 1 ELSE 0 END) AS no_match_po
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = bpm.reference_id
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss2 ON wss2.shipment_id = bpm.po_number
        WHERE bpm.create_type = 1
          AND bpm.business_type = 5
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
    """))
    for row in result3.fetchall():
        print(f"  total={row[0]}, no_match_via_reference_id={row[1]}, no_match_via_po_number={row[2]}")
