"""Check BPM table for process/close time columns to calculate responsiveness."""
import sys
sys.path.insert(0, '.')
from data_loader import _get_engine
from sqlalchemy import text

engine = _get_engine()
with engine.connect() as conn:
    # Find all time-related columns
    result = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'yamibuy_wh'
          AND table_name = 'wh_problem_solving_bpm'
          AND (column_name LIKE '%dt%' OR column_name LIKE '%time%'
               OR column_name LIKE '%close%' OR column_name LIKE '%finish%'
               OR column_name LIKE '%complete%' OR column_name LIKE '%process%'
               OR column_name LIKE '%resolve%' OR column_name LIKE '%handle%')
        ORDER BY column_name
    """))
    print("BPM time-related columns:")
    for row in result.fetchall():
        print(f"  {row[0]} ({row[1]})")

    # Sample a Seller BPM record to see what time values look like
    print("\n=== Sample Seller BPM with time fields ===")
    result2 = conn.execute(text("""
        SELECT in_dtm, edit_dtm,
               TIMESTAMPDIFF(HOUR, FROM_UNIXTIME(in_dtm), FROM_UNIXTIME(edit_dtm)) AS hours_diff
        FROM yamibuy_wh.wh_problem_solving_bpm
        WHERE business_type = 5
          AND create_type = 1
          AND in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
          AND edit_dtm > in_dtm
        LIMIT 10
    """))
    for row in result2.fetchall():
        print(f"  in_dtm={row[0]}, edit_dtm={row[1]}, hours_diff={row[2]}")
