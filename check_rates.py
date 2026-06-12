"""
Validation script part 3: Rate calculation correctness.
Picks a few vendors and cross-checks inbound qty vs BPM qty vs computed rate.
"""
import sys
sys.path.insert(0, '.')

from data_loader import _get_engine
from sqlalchemy import text

engine = _get_engine()

checks = [
    (
        "1. Top 5 Vendors by qty_received (180 days) — inbound volume",
        """
        SELECT pv.vendor_id, pv.vendor_name,
               SUM(ibb.quantity) AS qty_received,
               COUNT(ibb.item_number) AS po_sku_received
        FROM yamibuy_wh.wh_inbound_batch ibb
        LEFT JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
        LEFT JOIN yamibuy_po.po_purchase_order ppo ON ppo.po_number = ib.reference_id
        LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
        WHERE ib.reference_id NOT LIKE 'F%'
          AND ibb.item_number NOT LIKE '8%'
          AND ibb.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND pv.vendor_name IS NOT NULL
        GROUP BY pv.vendor_id, pv.vendor_name
        ORDER BY qty_received DESC
        LIMIT 5
        """
    ),
    (
        "2. BPM problem qty for those top vendors (criteria 1-6)",
        """
        SELECT pv.vendor_id, pv.vendor_name,
               SUM(CASE WHEN bpm.problem_type = 4 THEN bpm.item_qty ELSE 0 END) AS overage_qty,
               SUM(CASE WHEN bpm.problem_type = 3 THEN bpm.item_qty ELSE 0 END) AS damage_qty,
               SUM(CASE WHEN bpm.problem_type IN (5,6) THEN bpm.item_qty ELSE 0 END) AS upc_qty,
               SUM(CASE WHEN bpm.problem_type IN (1,2) THEN bpm.item_qty ELSE 0 END) AS exp_qty,
               SUM(CASE WHEN bpm.problem_type IN (7,8,9) THEN bpm.item_qty ELSE 0 END) AS po_qty,
               SUM(CASE WHEN bpm.problem_type = 10 THEN bpm.item_qty ELSE 0 END) AS no_data_qty
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_po.po_purchase_order ppo
            ON ppo.po_number = (CASE WHEN bpm.reference_id != '' THEN bpm.reference_id ELSE bpm.po_number END)
        LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
        WHERE bpm.create_type = 1
          AND bpm.business_type = 1
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND pv.vendor_name IS NOT NULL
          AND pv.vendor_id IN (
            SELECT pv2.vendor_id
            FROM yamibuy_wh.wh_inbound_batch ibb2
            LEFT JOIN yamibuy_wh.wh_inbound ib2 ON ib2.inbound_number = ibb2.inbound_number
            LEFT JOIN yamibuy_po.po_purchase_order ppo2 ON ppo2.po_number = ib2.reference_id
            LEFT JOIN yamibuy_po.po_vendor pv2 ON pv2.vendor_id = ppo2.vendor_id
            WHERE ib2.reference_id NOT LIKE 'F%'
              AND ibb2.item_number NOT LIKE '8%'
              AND ibb2.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
              AND pv2.vendor_name IS NOT NULL
            GROUP BY pv2.vendor_id
            ORDER BY SUM(ibb2.quantity) DESC
            LIMIT 5
          )
        GROUP BY pv.vendor_id, pv.vendor_name
        ORDER BY pv.vendor_id
        """
    ),
    (
        "3. Top 5 Sellers by qty_received",
        """
        SELECT wss.seller_id AS vendor_id, seller.vendor_name,
               SUM(ibb.quantity) AS qty_received,
               COUNT(ibb.item_number) AS po_sku_received
        FROM yamibuy_wh.wh_inbound_batch ibb
        LEFT JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = ib.reference_id
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = wss.seller_id
        WHERE ib.reference_id LIKE 'F%'
          AND ibb.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND seller.vendor_name IS NOT NULL
        GROUP BY wss.seller_id, seller.vendor_name
        ORDER BY qty_received DESC
        LIMIT 5
        """
    ),
    (
        "4. Seller BPM for top sellers (using reference_id JOIN)",
        """
        SELECT wss.seller_id AS vendor_id, seller.vendor_name,
               SUM(CASE WHEN bpm.problem_type = 4 THEN bpm.item_qty ELSE 0 END) AS overage_qty,
               SUM(CASE WHEN bpm.problem_type = 3 THEN bpm.item_qty ELSE 0 END) AS damage_qty,
               SUM(CASE WHEN bpm.problem_type IN (5,6) THEN bpm.item_qty ELSE 0 END) AS upc_qty,
               SUM(CASE WHEN bpm.problem_type IN (1,2) THEN bpm.item_qty ELSE 0 END) AS exp_qty
        FROM yamibuy_wh.wh_problem_solving_bpm bpm
        LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = bpm.reference_id
        LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = wss.seller_id
        WHERE bpm.create_type = 1
          AND bpm.business_type = 5
          AND bpm.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
          AND seller.vendor_name IS NOT NULL
        GROUP BY wss.seller_id, seller.vendor_name
        ORDER BY overage_qty DESC
        LIMIT 5
        """
    ),
    (
        "5. Sanity check: any vendor with overage_rate > 100%? (should be 0)",
        """
        SELECT COUNT(*) AS vendors_over_100pct
        FROM (
            SELECT pv.vendor_id,
                   SUM(ibb.quantity) AS qty,
                   COALESCE((
                       SELECT SUM(b.item_qty)
                       FROM yamibuy_wh.wh_problem_solving_bpm b
                       LEFT JOIN yamibuy_po.po_purchase_order p2
                           ON p2.po_number = (CASE WHEN b.reference_id != '' THEN b.reference_id ELSE b.po_number END)
                       WHERE b.create_type=1 AND b.business_type=1 AND b.problem_type=4
                         AND p2.vendor_id = pv.vendor_id
                         AND b.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
                   ), 0) AS overage
            FROM yamibuy_wh.wh_inbound_batch ibb
            LEFT JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
            LEFT JOIN yamibuy_po.po_purchase_order ppo ON ppo.po_number = ib.reference_id
            LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
            WHERE ib.reference_id NOT LIKE 'F%'
              AND ibb.item_number NOT LIKE '8%'
              AND ibb.in_dtm >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 180 DAY))
              AND pv.vendor_name IS NOT NULL
            GROUP BY pv.vendor_id
        ) t
        WHERE t.overage > t.qty
        """
    ),
]

print("=" * 60)
print("Rate Calculation Validation")
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
