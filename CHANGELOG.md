# Changelog

## [2026-06-12] — SQL Fix: BPM/QC direct vendor_id JOIN

### Problem
- Seller BPM (criteria 1-6): JOIN via `bpm.issue_po_number` → `wh_seller_shipment` had 0% match rate (field is empty for create_type=1)
- Seller QC (criteria 9): JOIN via `bpm.reference_id` → `wh_seller_shipment` had 0% match rate (field is empty for create_type=2)
- Vendor BPM/QC: Multi-table JOIN through `po_purchase_order` was fragile (13-14% miss rate for QC)

### Root Cause
The `wh_problem_solving_bpm` table has a direct `vendor_id` column that is populated 100% of the time for both Vendor (business_type=1) and Seller (business_type=5) records.

### Fix
All 4 BPM/QC queries now use `bpm.vendor_id` directly:
- Vendor BPM/QC: `JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = bpm.vendor_id`
- Seller BPM/QC: `JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = bpm.vendor_id`

### Result
| Query | Before | After |
|-------|--------|-------|
| Vendor BPM | 99.5% | 99.0% |
| Seller BPM | 0% → 94.7% (ref_id) | **99.9%** |
| Vendor QC | 86.2% | 86.8% |
| Seller QC | 0% | **100%** |

---

## [2026-06-12] — Data Model: Remove warehouse dimension

### Change
- Scoring is now per `vendor_id + business_type` (not per warehouse)
- Warehouse selector controls SQL query scope (only counts cases from LA/NJ/All)
- Each vendor/seller has exactly one row regardless of warehouse

### Reason
Same vendor can ship to both LA and NJ — splitting by warehouse creates duplicate vendor rows. Warehouse is a data scope filter, not a scoring dimension.

---

## [2026-06-12] — UI Fine-tuning

### Changes
- Detail tab: Score/Percentage/Actual Cases radio toggle
- Detail tab: Two search bars (ID exact, Name partial)
- Detail tab: AgGrid with frozen left columns
- Column order: Tier → Score → Name → ID → Type → Team → [criteria]
- Date range selector (Start/End) triggers DB reload
- Weight config in collapsible expanders with (%) labels
- Reset to Defaults button fixed (clears widget keys)
- Password protection for public deployment

---

## [2026-06-12] — Initial Release

- Full Streamlit dashboard with 5 tabs (Overview, Detail, Comparison, Impact Analysis, Export)
- Scoring engine: 10 criteria, configurable weights/thresholds/tier boundaries
- Data loading: MySQL with CSV fallback
- 122 property-based + unit tests
- Deployed to server via systemd (port 8502)
