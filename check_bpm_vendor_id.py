"""Check if bpm.vendor_id can be used directly for better matching."""
import sys
sys.path.insert(0, '.')
from data_loader import _get_engine
from sqlalchemy import text

engine = _get_engine()

with engine.connect() as conn:
    # Check Vendor BPM (business_type=1): does bpm.vendor_id match po_vendor.vendor_id?
    print("=== Vendor BPM: bpm.vendor_id vs JOIN-derived vendor_id ===")
    result = conn.execute(text("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN bpm.vendor_id IS NOT NULL AND bpm.vendor_id != 0 THEN 1 ELSE 0 END) AS has_vendor_id,
               SUM(CASE WHEN bpm.vendor_id = ppo.vendor_id THEN 1 ELSE 0 END) AS matches_po_vendor
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_po.po_purchase_order ppo
            ON ppo.po_number = (CASE WHEN bpm.reference_id != '' THEN bpm.reference_id ELSE bpm.po_number END)
        WHERE bpm.create_type = 1
          AND bpm.business_type = 1
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
    """))
    for row in result.fetchall():
        print(f"  total={row[0]}, has_vendor_id={row[1]}, matches_po_vendor={row[2]}")

    # Check Seller BPM (business_type=5): does bpm.vendor_id match seller_id?
    print("\n=== Seller BPM: bpm.vendor_id vs JOIN-derived seller_id ===")
    result2 = conn.execute(text("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN bpm.vendor_id IS NOT NULL AND bpm.vendor_id != 0 THEN 1 ELSE 0 END) AS has_vendor_id,
               SUM(CASE WHEN bpm.vendor_id = wss.seller_id THEN 1 ELSE 0 END) AS matches_seller_id
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = bpm.reference_id
        WHERE bpm.create_type = 1
          AND bpm.business_type = 5
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
    """))
    for row in result2.fetchall():
        print(f"  total={row[0]}, has_vendor_id={row[1]}, matches_seller_id={row[2]}")

    # Sample bpm.vendor_id for Seller records
    print("\n=== Seller BPM: sample bpm.vendor_id values ===")
    result3 = conn.execute(text("""
        SELECT bpm.vendor_id, bpm.reference_id, seller.vendor_name
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = bpm.vendor_id
        WHERE bpm.create_type = 1
          AND bpm.business_type = 5
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
          AND bpm.vendor_id IS NOT NULL AND bpm.vendor_id != 0
        LIMIT 5
    """))
    for row in result3.fetchall():
        print(f"  bpm.vendor_id={row[0]}, ref={row[1]!r}, seller_name={row[2]}")

    # Coverage: what % of ALL Seller BPM records have non-zero vendor_id?
    print("\n=== Seller BPM+QC coverage with bpm.vendor_id (all create_types) ===")
    result4 = conn.execute(text("""
        SELECT bpm.create_type,
               COUNT(*) AS total,
               SUM(CASE WHEN bpm.vendor_id IS NOT NULL AND bpm.vendor_id != 0 THEN 1 ELSE 0 END) AS has_vendor_id
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        WHERE bpm.business_type = 5
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
        GROUP BY bpm.create_type
    """))
    for row in result4.fetchall():
        print(f"  create_type={row[0]}, total={row[1]}, has_vendor_id={row[2]} ({row[2]/row[1]*100:.1f}%)")
