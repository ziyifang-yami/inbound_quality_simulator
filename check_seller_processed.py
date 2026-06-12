"""Check seller_processed field and validate responsiveness calculation."""
import sys
sys.path.insert(0, '.')
from data_loader import _get_engine
from sqlalchemy import text

engine = _get_engine()
with engine.connect() as conn:
    # Check seller_processed values distribution
    print("=== seller_processed distribution (Seller BPM, last 180 days) ===")
    result = conn.execute(text("""
        SELECT seller_processed, COUNT(*) AS cnt
        FROM yamibuy_wh.wh_problem_solving_bpm
        WHERE business_type = 5 AND create_type = 1
          AND in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
        GROUP BY seller_processed
    """))
    for row in result.fetchall():
        print(f"  seller_processed={row[0]}, count={row[1]}")

    # Average hours per seller (only where edit_dtm > in_dtm, i.e., processed)
    print("\n=== Top 5 sellers by avg responsiveness hours ===")
    result2 = conn.execute(text("""
        SELECT bpm.vendor_id, seller.vendor_name,
               AVG(TIMESTAMPDIFF(HOUR, FROM_UNIXTIME(bpm.in_dtm), FROM_UNIXTIME(bpm.edit_dtm))) AS avg_hours,
               COUNT(*) AS ticket_count
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = bpm.vendor_id
        WHERE bpm.business_type = 5 AND bpm.create_type = 1
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND bpm.edit_dtm > bpm.in_dtm
          AND seller.vendor_name IS NOT NULL
        GROUP BY bpm.vendor_id, seller.vendor_name
        ORDER BY avg_hours DESC
        LIMIT 5
    """))
    for row in result2.fetchall():
        print(f"  vendor_id={row[0]}, name={row[1]}, avg_hours={row[2]:.1f}, tickets={row[3]}")

    # And best responders
    print("\n=== Top 5 fastest responding sellers ===")
    result3 = conn.execute(text("""
        SELECT bpm.vendor_id, seller.vendor_name,
               AVG(TIMESTAMPDIFF(HOUR, FROM_UNIXTIME(bpm.in_dtm), FROM_UNIXTIME(bpm.edit_dtm))) AS avg_hours,
               COUNT(*) AS ticket_count
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = bpm.vendor_id
        WHERE bpm.business_type = 5 AND bpm.create_type = 1
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND bpm.edit_dtm > bpm.in_dtm
          AND seller.vendor_name IS NOT NULL
        GROUP BY bpm.vendor_id, seller.vendor_name
        HAVING ticket_count >= 3
        ORDER BY avg_hours ASC
        LIMIT 5
    """))
    for row in result3.fetchall():
        print(f"  vendor_id={row[0]}, name={row[1]}, avg_hours={row[2]:.1f}, tickets={row[3]}")
