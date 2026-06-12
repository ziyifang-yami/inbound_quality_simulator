"""
Quick validation script to check JOIN correctness in Vendor Inbound SQL.
Run: python check_joins.py
"""
import sys
sys.path.insert(0, '.')

from data_loader import _get_engine
from sqlalchemy import text

engine = _get_engine()

checks = [
    (
        "1. wh_inbound_batch → wh_inbound (orphan batches)",
        """
        SELECT COUNT(*) AS orphan_batches
        FROM yamibuy_wh.wh_inbound_batch ibb
        LEFT JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
        WHERE ib.inbound_number IS NULL
          AND ibb.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
        """
    ),
    (
        "2. wh_inbound → po_purchase_order (non-FBY, no PO match)",
        """
        SELECT COUNT(*) AS total_inbound,
               SUM(CASE WHEN ppo.po_number IS NULL THEN 1 ELSE 0 END) AS no_po_match
        FROM yamibuy_wh.wh_inbound ib
        LEFT JOIN yamibuy_po.po_purchase_order ppo ON ppo.po_number = ib.reference_id
        WHERE ib.reference_id NOT LIKE 'F%'
          AND ib.inbound_number IN (
            SELECT DISTINCT inbound_number FROM yamibuy_wh.wh_inbound_batch
            WHERE in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
          )
        """
    ),
    (
        "3. po_purchase_order → po_vendor (no vendor match)",
        """
        SELECT COUNT(*) AS total_po,
               SUM(CASE WHEN pv.vendor_id IS NULL THEN 1 ELSE 0 END) AS no_vendor_match
        FROM yamibuy_po.po_purchase_order ppo
        LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
        WHERE ppo.po_number NOT LIKE 'F%'
          AND ppo.po_number IN (
            SELECT DISTINCT reference_id FROM yamibuy_wh.wh_inbound ib
            WHERE ib.inbound_number IN (
              SELECT DISTINCT inbound_number FROM yamibuy_wh.wh_inbound_batch
              WHERE in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
            )
          )
        """
    ),
    (
        "4. im_item → category 3-level tree (sample 5 items)",
        """
        SELECT ii.item_number, ii.category_id,
               c3.category_id AS cat3_id, c3.category_name AS cat3_name,
               c2.category_id AS cat2_id, c2.category_name AS cat2_name,
               c1.category_id AS cat1_id, c1.category_name AS cat1_name
        FROM yamibuy_im.im_item ii
        LEFT JOIN yamibuy_im.im_category c3 ON c3.category_id = ii.category_id
        LEFT JOIN yamibuy_im.im_category c2 ON c2.category_id = c3.parent_category_id
        LEFT JOIN yamibuy_im.im_category c1 ON c1.category_id = c2.parent_category_id
        WHERE ii.item_number NOT LIKE '8%'
        LIMIT 5
        """
    ),
    (
        "5. Final Vendor count (last 180 days)",
        """
        SELECT COUNT(DISTINCT pv.vendor_id) AS vendor_count,
               COUNT(*) AS total_batch_rows
        FROM yamibuy_wh.wh_inbound_batch ibb
        LEFT JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
        LEFT JOIN yamibuy_po.po_purchase_order ppo ON ppo.po_number = ib.reference_id
        LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
        WHERE ib.reference_id NOT LIKE 'F%'
          AND ibb.item_number NOT LIKE '8%'
          AND ibb.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND pv.vendor_name IS NOT NULL
        """
    ),
    (
        "6. Seller inbound count (last 180 days)",
        """
        SELECT COUNT(DISTINCT wss.seller_id) AS seller_count,
               COUNT(*) AS total_batch_rows
        FROM yamibuy_wh.wh_inbound_batch ibb
        LEFT JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = ib.reference_id
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = wss.seller_id
        WHERE ib.reference_id LIKE 'F%'
          AND ibb.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND seller.vendor_name IS NOT NULL
        """
    ),
]

print("=" * 60)
print("SQL JOIN Validation Checks")
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
        except Exception as e:
            print(f"    ❌ ERROR: {e}")

print(f"\n{'=' * 60}")
print("Done.")
