# 评分 Criteria 与权重说明

> **来源**: [Google Sheet - Ops 入库质量 Criteria Details](https://docs.google.com/spreadsheets/d/1HNEzs65WF03vaEY1flrb9vOHJJHBID30QSo_-ybU6sE/edit?gid=338232131#gid=338232131)  
> **文档更新**: 2026-07-20

---

## 1. 评分维度总览（10 项 Criteria）

| # | Criteria ID | 中文名称 | 英文名称 | 计算公式 |
|---|---|---|---|---|
| 1 | damage | 入库破损率 | Inbound Defect Rate | Damage QTY / Received QTY |
| 2 | exp_error | 过期/保质期问题率 | Expiry/Shelf Life Issue Rate | EXP QTY / Received QTY |
| 3 | overage | 超量问题率 | Overage Issue Rate | Overage QTY / Received QTY |
| 4 | spec_image_error | 规格/图片不符率 | Spec/Pics Not Aligned Rate | Issues / TTL PO SKUs |
| 5 | no_data | 货物不一致率 | Wrong Items Rate | Issued units / Received QTY |
| 6 | upc_error | 标签/条码不准确率 | Label/Barcode Inaccuracy Rate | Issued units / Received QTY |
| 7 | packaging_error | 包装问题率 | Packaging Issue Rate | Issues / TTL PO SKUs |
| 8 | po_error | 文档准确率 | Documentation Inaccuracy Rate | Issued SKU / TTL PO SKUs |
| 9 | responsiveness | 响应速度 | Responsiveness | Avg processed days |
| 10 | poor_quality | QC 抽检问题率 | QC Random Check Issue Rate | Issued units / TTL PO units |

---

## 2. 权重配置（Weight）

权重总和 = 100%。不同 business_type 使用不同权重：

### Vendor 权重

| Criteria | 权重 |
|----------|:----:|
| damage (破损) | **15%** |
| exp_error (过期) | **15%** |
| overage (超量) | **15%** |
| spec_image_error (规格/图片) | 5% |
| no_data (货物不一致) | **10%** |
| upc_error (UPC/条码) | **10%** |
| packaging_error (包装) | **10%** |
| po_error (文档) | 5% |
| responsiveness (响应速度) | **0%** |
| poor_quality (QC 抽检) | **15%** |

### Seller 权重

| Criteria | 权重 |
|----------|:----:|
| damage (破损) | **15%** |
| exp_error (过期) | **15%** |
| overage (超量) | **10%** |
| spec_image_error (规格/图片) | **15%** |
| no_data (货物不一致) | **10%** |
| upc_error (UPC/条码) | **10%** |
| packaging_error (包装) | 5% |
| po_error (文档) | **10%** |
| responsiveness (响应速度) | 5% |
| poor_quality (QC 抽检) | 5% |

### 权重差异说明

| Criteria | Vendor | Seller | 差异原因 |
|----------|:------:|:------:|----------|
| overage | 15% | 10% | Vendor PO 数量更可控，超量问题权重更高 |
| spec_image_error | 5% | 15% | Seller 自行上架，图片/规格一致性更重要 |
| packaging_error | 10% | 5% | Vendor 大批量入库，包装标准化要求更高 |
| po_error | 5% | 10% | Seller 文档管理能力弱，需更高关注 |
| responsiveness | 0% | 5% | Vendor 不需要响应BPM；Seller 需要配合处理 |
| poor_quality | 15% | 5% | Vendor 品控要求高，QC 抽检权重大 |

---

## 3. 评级阈值（Grade Thresholds）

每个 criteria 的 rate 映射到 4 档评级分数:

| 评级 | 分数 | 含义 |
|------|:----:|------|
| A | 100 | 优秀（rate ≤ A阈值）|
| B | 80 | 良好（A < rate ≤ B阈值）|
| C | 60 | 需改进（B < rate ≤ C阈值）|
| D | 20 | 差（rate > C阈值）|

### Vendor 阈值表

| Criteria | A 阈值 | B 阈值 | C 阈值 |
|----------|:------:|:------:|:------:|
| damage | <0.01% | 0.01-0.05% | 0.05-0.25% |
| exp_error | <0.01% | 0.01-1% | 1-5% |
| overage | <0.01% | 0.01-0.5% | 0.5-2% |
| spec_image_error | <0.01% | 0.01-3% | 3-5% |
| no_data | <0.01% | 0.01-0.5% | 0.5-5% |
| upc_error | <0.01% | 0.01-0.5% | 0.5-5% |
| packaging_error | <0.01% | 0.01-0.5% | 0.5-1% |
| po_error | <0.01% | 0.01-1% | 1-5% |
| responsiveness | <1.5 天 | 1.5-3 天 | 3-7 天 |
| poor_quality | <0.01% | 0.01-0.05% | 0.05-0.2% |

### Seller 阈值表

| Criteria | A 阈值 | B 阈值 | C 阈值 |
|----------|:------:|:------:|:------:|
| damage | <0.01% | 0.01-0.3% | 0.3-1.5% |
| exp_error | <0.01% | 0.01-1% | 1-5% |
| overage | <0.01% | 0.01-0.5% | 0.5-2% |
| spec_image_error | <0.01% | 0.01-3% | 3-5% |
| no_data | <0.01% | 0.01-0.5% | 0.5-5% |
| upc_error | <0.01% | 0.01-0.5% | 0.5-5% |
| packaging_error | <0.01% | 0.01-0.5% | 0.5-1% |
| po_error | <0.01% | 0.01-1% | 1-5% |
| responsiveness | <1.5 天 | 1.5-3 天 | 3-7 天 |
| poor_quality | <0.01% | 0.01-0.05% | 0.05-0.2% |

**注**: Seller damage 阈值比 Vendor 宽松（B=0.3% vs 0.05%，C=1.5% vs 0.25%），因为 Seller 发货包装标准不如 Vendor 统一。

---

## 4. 评分计算逻辑

### Step 1: Rate → Grade 转换

```python
def compute_grade(rate, thresholds):
    if rate <= thresholds['A']:
        return 100    # 优秀
    elif rate <= thresholds['B']:
        return 80     # 良好
    elif rate <= thresholds['C']:
        return 60     # 需改进
    else:
        return 20     # 差
```

### Step 2: 加权总分计算

```
total_score = Σ (grade_i × weight_i / 100)
```

**示例**（Vendor, 所有 criteria 评级为 A = 100 分）:
```
total_score = 100×15% + 100×15% + 100×15% + 100×5% + 100×10% 
            + 100×10% + 100×10% + 100×5% + 100×0% + 100×15%
            = 100
```

### Step 3: Tier 分级

| Tier | 条件 | 含义 |
|:----:|------|------|
| A | score ≥ 95 | 优质供应商 |
| B | 80 ≤ score < 95 | 良好供应商 |
| C | 65 ≤ score < 80 | 需改进供应商 |
| D | score < 65 | 高风险供应商 |

---

## 5. 数据来源对照

| Criteria | 数据来源表 | 核心字段 | 筛选条件 |
|----------|-----------|---------|----------|
| damage | wh_problem_solving_bpm | problem_type=3, item_qty | create_type=1 |
| exp_error | wh_problem_solving_bpm | problem_type IN (1,2), item_qty | create_type=1 |
| overage | wh_problem_solving_bpm | problem_type=4, item_qty | create_type=1 |
| spec_image_error | wh_inbound_batch | weight_error (Vendor), weight_error OR image_error (Seller) | 入库时记录 |
| no_data | wh_problem_solving_bpm | problem_type=10, item_qty | create_type=1 |
| upc_error | wh_problem_solving_bpm | problem_type IN (5,6), item_qty | create_type=1 |
| packaging_error | wh_inbound_batch | problem_report IS NOT NULL | 入库时记录 |
| po_error | wh_problem_solving_bpm | problem_type IN (7,8,9), 计数 | create_type=1 |
| responsiveness | wh_problem_solving_bpm | TIMESTAMPDIFF(in_dtm, edit_dtm) | Seller only, edit_dtm > in_dtm |
| poor_quality | wh_problem_solving_bpm | comment LIKE '%poor quality%' | create_type=2, problem_type IN (3,6) |

---

## 6. BPM problem_type 完整编码表

| problem_type | 问题类别 | 对应 criteria |
|:---:|---|---|
| 1 | 过期 - 已过期 | exp_error |
| 2 | 过期 - 保质期不足 | exp_error |
| 3 | 破损 | damage |
| 4 | 超量 | overage |
| 5 | UPC 不匹配 | upc_error |
| 6 | 标签错误 | upc_error |
| 7 | PO 文档问题 - 数量 | po_error |
| 8 | PO 文档问题 - 品种 | po_error |
| 9 | PO 文档问题 - 其他 | po_error |
| 10 | 货物不一致 / Wrong Item | no_data |

---

## 7. BPM create_type 与 business_type 说明

| create_type | 含义 | 用途 |
|:---:|---|---|
| 1 | 入库时创建的工单 | 用于 criteria 1-6, 8, 9 |
| 2 | QC 抽检创建的工单 | 用于 criteria 10 (poor_quality) |

| business_type | 含义 |
|:---:|---|
| 1 | Vendor |
| 5 | Seller |

