"""Check po_purchase_order date columns."""
import sys
sys.path.insert(0, '.')
from data_loader import _get_engine
from sqlalchemy import text

engine = _get_engine()
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'yamibuy_po'
          AND table_name = 'po_purchase_order'
          AND (column_name LIKE '%dt%' OR column_name LIKE '%date%' OR column_name LIKE '%time%' OR column_name LIKE '%create%')
    """))
    print("po_purchase_order date columns:")
    for row in result.fetchall():
        print(f"  {row[0]}")

    # Also check wh_seller_shipment
    result2 = conn.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'yamibuy_wh'
          AND table_name = 'wh_seller_shipment'
          AND (column_name LIKE '%dt%' OR column_name LIKE '%date%' OR column_name LIKE '%time%' OR column_name LIKE '%create%')
    """))
    print("\nwh_seller_shipment date columns:")
    for row in result2.fetchall():
        print(f"  {row[0]}")
