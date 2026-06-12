"""Verify new BPM/QC SQL using bpm.vendor_id direct JOIN."""
import sys
sys.path.insert(0, '.')
from data_loader import _get_engine
from sqlalchemy import text

engine = _get_engine()

checks = [
    (
        "1. Vendor BPM (bpm.vendor_id → po_vendor): match rate",
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN pv.vendor_id IS NULL THEN 1 ELSE 0 END) AS no_match
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = bpm.vendor_id
        WHERE bpm.create_type = 1 AND bpm.business_type = 1
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND bpm.vendor_id IS NOT NULL AND bpm.vendor_id != 0
        """
    ),
    (
        "2. Seller BPM (bpm.vendor_id → xysc_vendor_info): match rate",
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN seller.vendor_id IS NULL THEN 1 ELSE 0 END) AS no_match
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = bpm.vendor_id
        WHERE bpm.create_type = 1 AND bpm.business_type = 5
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND bpm.vendor_id IS NOT NULL AND bpm.vendor_id != 0
        """
    ),
    (
        "3. Vendor QC (bpm.vendor_id → po_vendor): match rate",
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN pv.vendor_id IS NULL THEN 1 ELSE 0 END) AS no_match
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = bpm.vendor_id
        WHERE bpm.create_type = 2 AND bpm.business_type = 1 AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND bpm.vendor_id IS NOT NULL AND bpm.vendor_id != 0
        """
    ),
    (
        "4. Seller QC (bpm.vendor_id → xysc_vendor_info): match rate",
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN seller.vendor_id IS NULL THEN 1 ELSE 0 END) AS no_match
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = bpm.vendor_id
        WHERE bpm.create_type = 2 AND bpm.business_type = 5 AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND bpm.vendor_id IS NOT NULL AND bpm.vendor_id != 0
        """
    ),
    (
        "5. Seller BPM top 5 (verify data makes sense)",
        """
        SELECT seller.vendor_name, bpm.vendor_id,
               SUM(CASE WHEN bpm.problem_type = 4 THEN bpm.item_qty ELSE 0 END) AS overage_qty,
               SUM(CASE WHEN bpm.problem_type = 3 THEN bpm.item_qty ELSE 0 END) AS damage_qty,
               SUM(bpm.item_qty) AS total_qty
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = bpm.vendor_id
        WHERE bpm.create_type = 1 AND bpm.business_type = 5
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND seller.vendor_name IS NOT NULL
        GROUP BY seller.vendor_name, bpm.vendor_id
        ORDER BY total_qty DESC
        LIMIT 5
        """
    ),
    (
        "6. Seller QC top 5 (verify data makes sense)",
        """
        SELECT seller.vendor_name, bpm.vendor_id,
               SUM(CASE WHEN bpm.comment LIKE '%quality%' THEN bpm.item_qty ELSE 0 END) AS poor_quality_qty,
               SUM(bpm.item_qty) AS total_qty
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = bpm.vendor_id
        WHERE bpm.create_type = 2 AND bpm.business_type = 5 AND bpm.problem_type = 3
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND seller.vendor_name IS NOT NULL
        GROUP BY seller.vendor_name, bpm.vendor_id
        ORDER BY poor_quality_qty DESC
        LIMIT 5
        """
    ),
]

print("=" * 60)
print("New BPM/QC SQL Validation (using bpm.vendor_id)")
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
