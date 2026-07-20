# Simulator SQL 数据调用逻辑文档

> **项目**: Inbound Quality Score Simulator  
> **数据源**: MySQL (rds.g3.yamibuy.net) + AWS Athena  
> **时间窗口**: 默认过去 180 天  
> **文档更新**: 2026-07-13

---

## 1. 数据流概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据加载流程                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  MySQL DB ──┬── Inbound Volume SQL ──┐                           │
│             ├── BPM Issue SQL ────────┤── merge ── compute_rates │
│             ├── QC SQL ──────────────┤         ── scoring        │
│             └── Responsiveness SQL ──┘         ── tier classify  │
│                                                                   │
│  Athena ──── Seller AM Mapping ──── owner info                   │
│  MySQL ───── Vendor PM Mapping ──── owner info                   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心数据表

| 数据库 | 表名 | 用途 |
|--------|------|------|
| yamibuy_wh | `wh_inbound_batch` | 入库明细（item级别，含数量、图片/重量异常、问题报告）|
| yamibuy_wh | `wh_inbound` | 入库主表（reference_id 关联 PO/Shipment）|
| yamibuy_wh | `wh_problem_solving_bpm` | BPM 问题工单（含 problem_type、item_qty）|
| yamibuy_wh | `wh_seller_shipment` | Seller 发货单（seller_id ↔ reference_id）|
| yamibuy_po | `po_purchase_order` | PO 采购单（关联 vendor_id）|
| yamibuy_po | `po_vendor` | Vendor 主数据（vendor_name）|
| yamibuy_po | `po_pm_vendor` | Vendor-PM 关系表 |
| yamibuy_im | `im_item` | 商品主数据 |
| yamibuy_im | `im_category` | 品类层级（用于 Food/Non-food 分组）|
| yamibuy_im | `im_pm` | PM 信息表 |
| yamibuy_master | `xysc_vendor_info` | Seller 主数据（vendor_name）|
| yamibuy_central (Athena) | `admin_seller` | Seller-AM 关系表 |
| yamibuy_master (Athena) | `xysc_admin_user` | 管理员用户（AM name）|

---

## 3. SQL 查询详解

### 3.1 Vendor 入库量查询 (`_build_vendor_inbound_sql`)

**目的**: 获取 Vendor 的入库数量、PO 数、SKU 数，以及从 inbound_batch 直接提取的 spec_image_error 和 packaging_error 原始数量。

```sql
SELECT
    bb.vendor_name,
    bb.vendor_id,
    'Vendor' AS business_type,
    bb.team,
    COUNT(DISTINCT bb.reference_id) AS po_received,
    SUM(bb.quantity) AS qty_received,
    COUNT(bb.item_number) AS po_sku_received,
    SUM(bb.weight_error) AS spec_image_error,
    SUM(CASE WHEN bb.problem_report IS NOT NULL AND bb.problem_report != '' THEN 1 ELSE 0 END) AS packaging_error
FROM (
    SELECT
        ib.reference_id,
        ib.inbound_number,
        ibb.item_number,
        ibb.quantity,
        pv.vendor_name,
        ib.warehouse_number,
        pv.vendor_id,
        ibb.image_error,
        ibb.weight_error,
        ibb.problem_report,
        CASE
            WHEN c1.category_id IN (1, 301, 310) THEN 'Food'
            WHEN c1.category_id IN (2, 7, 10, 11, 320, 334, 342, 350) THEN 'Non-food'
            ELSE 'Other'
        END AS team
    FROM yamibuy_wh.wh_inbound_batch ibb
    LEFT JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
    LEFT JOIN yamibuy_po.po_purchase_order ppo ON ppo.po_number = ib.reference_id
    LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
    LEFT JOIN yamibuy_im.im_item ii ON ii.item_number = ibb.item_number
    LEFT JOIN yamibuy_im.im_category c3 ON c3.category_id = ii.category_id
    LEFT JOIN yamibuy_im.im_category c2 ON c2.category_id = c3.parent_category_id
    LEFT JOIN yamibuy_im.im_category c1 ON c1.category_id = c2.parent_category_id
    WHERE ib.reference_id NOT LIKE 'F%'            -- 排除 Seller shipment
      AND ibb.item_number NOT LIKE '8%'            -- 排除特殊 item
      AND ibb.in_dtm >= UNIX_TIMESTAMP('{start}')
      AND ibb.in_dtm < UNIX_TIMESTAMP('{end}')
      {warehouse_filter}
) bb
WHERE bb.vendor_name IS NOT NULL
GROUP BY 1, 2, 3, 4
```

**关键逻辑**:
- `reference_id NOT LIKE 'F%'` 区分 Vendor（PO号）和 Seller（F开头的 shipment）
- 通过三级品类 JOIN 确定 Food/Non-food team
- `weight_error` 字段作为 spec_image_error 的计数
- `problem_report` 非空则计为 packaging_error

---

### 3.2 Seller 入库量查询 (`_build_seller_inbound_sql`)

**目的**: 与 Vendor 类似，但 JOIN 路径不同（通过 `wh_seller_shipment`）。

```sql
SELECT
    bb.vendor_name,
    bb.vendor_id,
    'Seller' AS business_type,
    'TTL' AS team,
    COUNT(DISTINCT bb.reference_id) AS po_received,
    SUM(bb.quantity) AS qty_received,
    COUNT(bb.item_number) AS po_sku_received,
    SUM(CASE WHEN bb.weight_error = 1 OR bb.image_error = 1 THEN 1 ELSE 0 END) AS spec_image_error,
    SUM(CASE WHEN bb.problem_report IS NOT NULL AND bb.problem_report != '' THEN 1 ELSE 0 END) AS packaging_error
FROM (
    SELECT
        ib.reference_id,
        ib.inbound_number,
        ibb.item_number,
        ibb.quantity,
        seller.vendor_name,
        ib.warehouse_number,
        wss.seller_id AS vendor_id,
        ibb.image_error,
        ibb.weight_error,
        ibb.problem_report
    FROM yamibuy_wh.wh_inbound_batch ibb
    LEFT JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
    LEFT JOIN yamibuy_wh.wh_seller_shipment wss ON wss.shipment_id = ib.reference_id
    LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = wss.seller_id
    WHERE ib.reference_id LIKE 'F%'                -- 只取 Seller shipment
      AND ibb.in_dtm >= UNIX_TIMESTAMP('{start}')
      AND ibb.in_dtm < UNIX_TIMESTAMP('{end}')
      {warehouse_filter}
) bb
WHERE bb.vendor_name IS NOT NULL
GROUP BY 1, 2, 3, 4
```

**与 Vendor 的区别**:
- `reference_id LIKE 'F%'` 过滤 Seller 数据
- 通过 `wh_seller_shipment.shipment_id` 关联入库单
- Seller 的 spec_image_error = `weight_error = 1 OR image_error = 1`
- 没有 team 分组（Seller 统一为 'TTL'）

---

### 3.3 Vendor BPM 问题工单查询 (`_build_vendor_bpm_sql`)

**目的**: 从 BPM 表获取 Vendor 的 6 类问题数量（criteria 1-6）。

```sql
SELECT
    pv.vendor_name,
    bpm.vendor_id,
    'Vendor' AS business_type,
    SUM(CASE WHEN bpm.problem_type = 4 THEN bpm.item_qty ELSE 0 END) AS overage_qty,
    SUM(CASE WHEN bpm.problem_type = 3 THEN bpm.item_qty ELSE 0 END) AS damage_qty,
    SUM(CASE WHEN bpm.problem_type IN (5, 6) THEN bpm.item_qty ELSE 0 END) AS upc_qty,
    SUM(CASE WHEN bpm.problem_type IN (1, 2) THEN bpm.item_qty ELSE 0 END) AS exp_qty,
    SUM(CASE WHEN bpm.problem_type IN (7, 8, 9) THEN 1 ELSE 0 END) AS po_qty,
    SUM(CASE WHEN bpm.problem_type = 10 THEN bpm.item_qty ELSE 0 END) AS no_data_qty
FROM yamibuy_wh.wh_problem_solving_bpm bpm
LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = bpm.vendor_id
WHERE bpm.create_type = 1           -- 入库创建的工单
  AND bpm.business_type = 1         -- Vendor
  AND bpm.in_dtm >= UNIX_TIMESTAMP('{start}')
  AND bpm.in_dtm < UNIX_TIMESTAMP('{end}')
  {warehouse_filter}
  AND pv.vendor_name IS NOT NULL
  AND pv.vendor_name NOT LIKE '%测试%'
GROUP BY 1, 2, 3
```

**problem_type 映射**:
| problem_type | 含义 | 对应字段 |
|---|---|---|
| 1, 2 | 过期/保质期问题 | exp_qty |
| 3 | 破损 | damage_qty |
| 4 | 超量 | overage_qty |
| 5, 6 | UPC/条码问题 | upc_qty |
| 7, 8, 9 | PO/文档问题 | po_qty (按工单计数，不按数量) |
| 10 | 货物不一致 | no_data_qty |

**注意**: `po_qty` 使用 `SUM(...THEN 1 ELSE 0)` 按工单条数计数，而非 `item_qty`。

---

### 3.4 Seller BPM 问题工单查询 (`_build_seller_bpm_sql`)

与 Vendor BPM 结构相同，差异点:
- `bpm.business_type = 5` (Seller)
- JOIN `yamibuy_master.xysc_vendor_info seller` 而非 `po_vendor`

---

### 3.5 Vendor QC 抽检查询 (`_build_vendor_qc_sql`)

**目的**: 获取 QC 抽检发现的质量问题数量（criteria 10: poor_quality）。

```sql
SELECT
    pv.vendor_name,
    bpm.vendor_id,
    'Vendor' AS business_type,
    SUM(CASE WHEN bpm.comment LIKE '%poor quality%' THEN bpm.item_qty ELSE 0 END) AS poor_quality_qty
FROM yamibuy_wh.wh_problem_solving_bpm bpm
LEFT JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = bpm.vendor_id
WHERE bpm.create_type = 2           -- QC 创建的工单
  AND bpm.business_type = 1         -- Vendor
  AND bpm.problem_type IN (3, 6)    -- 破损 或 UPC 问题（QC 场景）
  AND bpm.in_dtm >= UNIX_TIMESTAMP('{start}')
  AND bpm.in_dtm < UNIX_TIMESTAMP('{end}')
  {warehouse_filter}
  AND pv.vendor_name IS NOT NULL
  AND pv.vendor_name NOT LIKE '%测试%'
GROUP BY 1, 2, 3
```

**关键**:
- `create_type = 2` 区分 QC 抽检创建 vs 入库时创建
- `comment LIKE '%poor quality%'` 进一步筛选 poor quality 标记

---

### 3.6 Seller QC 抽检查询 (`_build_seller_qc_sql`)

与 Vendor QC 结构相同，差异: `bpm.business_type = 5`。

---

### 3.7 Seller 响应速度查询 (`_build_seller_responsiveness_sql`)

**目的**: 计算 Seller 处理 BPM 工单的平均响应时间（criteria 9）。

```sql
SELECT
    bpm.vendor_id,
    seller.vendor_name,
    'Seller' AS business_type,
    AVG(TIMESTAMPDIFF(HOUR, FROM_UNIXTIME(bpm.in_dtm), FROM_UNIXTIME(bpm.edit_dtm))) AS responsiveness_hours
FROM yamibuy_wh.wh_problem_solving_bpm bpm
LEFT JOIN yamibuy_master.xysc_vendor_info seller ON seller.vendor_id = bpm.vendor_id
WHERE bpm.business_type = 5
  AND bpm.create_type = 1
  AND bpm.edit_dtm > bpm.in_dtm     -- 只计算实际被处理的工单
  AND bpm.in_dtm >= UNIX_TIMESTAMP('{start}')
  AND bpm.in_dtm < UNIX_TIMESTAMP('{end}')
  {warehouse_filter}
  AND seller.vendor_name IS NOT NULL
  AND seller.vendor_name NOT LIKE '%测试%'
GROUP BY 1, 2, 3
```

**注意**: 
- Vendor 的 responsiveness 权重为 0%，因此不查询 Vendor 响应速度
- 实际用于评分的是 `avg_days` = `responsiveness_hours / 24`

---

### 3.8 Seller 响应速度（实际评分用）

在 `load_data_from_db()` 中额外执行的简化版本：

```sql
SELECT bpm.vendor_id,
       AVG(TIMESTAMPDIFF(HOUR, FROM_UNIXTIME(bpm.in_dtm), FROM_UNIXTIME(bpm.edit_dtm)) / 24.0) AS avg_days
FROM yamibuy_wh.wh_problem_solving_bpm bpm
WHERE bpm.business_type = 5
  AND bpm.create_type = 1
  AND bpm.edit_dtm > bpm.in_dtm
  AND bpm.in_dtm >= UNIX_TIMESTAMP('{start}')
  AND bpm.in_dtm < UNIX_TIMESTAMP('{end}')
  {warehouse_filter}
  AND bpm.vendor_id IS NOT NULL AND bpm.vendor_id != 0
GROUP BY bpm.vendor_id
```

---

### 3.9 Vendor PM 关系查询 (`_load_owner_info`)

```sql
SELECT pmv.vendor_id, pm.PM_name AS pm_name, pmv.is_primary
FROM yamibuy_po.po_pm_vendor pmv
JOIN yamibuy_im.im_pm pm ON pm.PM_id = CAST(pmv.pm_id AS CHAR)
WHERE pm.status = 'A'
  AND pmv.deleted = 0
```

---

### 3.10 Seller AM 关系查询 (Athena)

```sql
SELECT a.seller_id, a.user_id, u.user_name AS am_name
FROM yamibuy_central.admin_seller a
LEFT JOIN yamibuy_master.xysc_admin_user u ON u.user_id = a.user_id
```

---

### 3.11 Inactive Vendors/Sellers 查询

**Vendor**: 过去一年有 PO 但评分窗口无入库记录
```sql
SELECT pv.vendor_id, pv.vendor_name, 'Vendor' AS business_type,
       MAX(ppo.in_dtm) AS last_po_date
FROM yamibuy_po.po_purchase_order ppo
JOIN yamibuy_po.po_vendor pv ON pv.vendor_id = ppo.vendor_id
WHERE ppo.po_number NOT LIKE 'F%'
  AND ppo.in_dtm >= '{one_year_ago}'
  AND ppo.in_dtm < '{end_date}'
  AND pv.vendor_name IS NOT NULL
  AND pv.vendor_name NOT LIKE '%测试%'
  AND pv.vendor_id NOT IN (
      -- 排除在评分窗口内有入库的 vendor
      SELECT DISTINCT ppo2.vendor_id
      FROM yamibuy_wh.wh_inbound_batch ibb
      JOIN yamibuy_wh.wh_inbound ib ON ib.inbound_number = ibb.inbound_number
      JOIN yamibuy_po.po_purchase_order ppo2 ON ppo2.po_number = ib.reference_id
      WHERE ib.reference_id NOT LIKE 'F%'
        AND ibb.item_number NOT LIKE '8%'
        AND ibb.in_dtm >= UNIX_TIMESTAMP('{start_date}')
        AND ibb.in_dtm < UNIX_TIMESTAMP('{end_date}')
  )
GROUP BY pv.vendor_id, pv.vendor_name
```

**Seller**: 过去一年有 shipment 但评分窗口无入库记录（逻辑类似，通过 `wh_seller_shipment` 查询）。

---

## 4. 数据合并与 Rate 计算逻辑 (`_compute_rates`)

### 合并流程

```
inbound_df (入库量)
    ↓ aggregate by [vendor_id, business_type] (sum qty/sku/errors)
    ↓ LEFT JOIN bpm_df on [vendor_id, business_type]
    ↓ LEFT JOIN qc_df on [vendor_id, business_type]
    ↓ LEFT JOIN resp_df (Seller only)
    ↓ compute rates
    = final scored dataset
```

### Rate 计算公式

| 指标 | 公式 | 分母 |
|------|------|------|
| damage_rate | damage_qty / qty_received | qty_received |
| exp_error_rate | exp_qty / qty_received | qty_received |
| overage_rate | overage_qty / qty_received | qty_received |
| upc_error_rate | upc_qty / qty_received | qty_received |
| no_data_rate | no_data_qty / qty_received | qty_received |
| poor_quality_rate | poor_quality_qty / qty_received | qty_received |
| spec_image_error_rate | spec_image_error / po_sku_received | po_sku_received |
| packaging_error_rate | packaging_error / po_sku_received | po_sku_received |
| po_error_rate | po_qty / po_sku_received | po_sku_received |
| responsiveness_days | AVG(TIMESTAMPDIFF / 24) | (直接取平均值) |

**除零处理**: 当分母为 0 时，rate = 0（使用 `fillna(0)`）。

---

## 5. Warehouse 过滤逻辑

| 选项 | inbound 过滤 | BPM 过滤 |
|------|-------------|----------|
| All | 无过滤 | 无过滤 |
| LA | `AND ib.warehouse_number = 001` | `AND bpm.warehouse_number = 001` |
| NJ | `AND ib.warehouse_number = 002` | `AND bpm.warehouse_number = 002` |

Warehouse 是数据范围过滤器，不是评分维度。每个 vendor/seller 只有一行输出。

---

## 6. 时间戳说明

- `wh_inbound_batch.in_dtm`: UNIX timestamp（秒），用于入库时间范围过滤
- `wh_problem_solving_bpm.in_dtm`: UNIX timestamp（秒），工单创建时间
- `wh_problem_solving_bpm.edit_dtm`: UNIX timestamp（秒），工单最后编辑时间
- 日期过滤使用 `UNIX_TIMESTAMP('YYYY-MM-DD')` 转换

