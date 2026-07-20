# Inbound Quality Score Simulator — Roadmap

> **项目**: Inbound Quality Score Simulator  
> **当前版本**: v1.0 (2026-06-12 初始发布)  
> **文档更新**: 2026-07-13

---

## 1. 项目背景

Simulator 是一个 Streamlit 仪表板，用于评估 Vendor/Seller 的入库质量表现。系统通过 10 个质量维度对供应商进行评分和分级（A/B/C/D），支持参数模拟（调整权重/阈值/分级边界），帮助 Ops 团队决策供应商管理策略。

**评分数据来源**:
- Google Sheet: [Ops 入库质量 - Criteria Details](https://docs.google.com/spreadsheets/d/1HNEzs65WF03vaEY1flrb9vOHJJHBID30QSo_-ybU6sE/edit?gid=338232131#gid=338232131)
- MySQL 数据库: 入库量 + BPM 问题工单 + QC 抽检
- AWS Athena: Seller AM 关系数据

---

## 2. 已完成里程碑

### ✅ Phase 1 — 核心引擎 (2026-06-12)
- [x] 10 维度评分引擎 (scoring.py)
- [x] MySQL 数据加载 + CSV 回退 (data_loader.py)
- [x] 可配置权重/阈值/Tier边界
- [x] Streamlit 5 Tab 仪表板 (Overview, Detail, Comparison, Impact, Export)
- [x] 122 个测试（单元测试 + Hypothesis 属性测试）
- [x] 密码保护
- [x] 部署到服务器 (port 8502, systemd)

### ✅ Phase 1.1 — SQL 修复 (2026-06-12)
- [x] BPM/QC 查询改用 `bpm.vendor_id` 直连（修复 Seller 0% 匹配率问题）
- [x] 移除 warehouse 作为评分维度（改为数据范围过滤）
- [x] Vendor QC 匹配率: 86.2% → 86.8%
- [x] Seller BPM 匹配率: 0% → 99.9%

### ✅ Phase 1.2 — UI 增强 (2026-06-12)
- [x] AgGrid 冻结列 + 搜索
- [x] Score/Percentage/Actual Cases 切换
- [x] 日期选择器触发 DB reload
- [x] Owner (PM/AM) 展示

---

## 3. 当前进行中

### 🔄 Phase 2 — 数据准确性与完整性
- [ ] 验证 `spec_image_error` 数据源准确性（weight_error vs image_error 字段含义确认）
- [ ] 分析 BPM `problem_type` 编码与实际场景对应关系的完整性
- [ ] 确认 QC `comment LIKE '%poor quality%'` 的覆盖率
- [ ] 调研是否有遗漏的 problem_type 需要纳入评分

---

## 4. 后续 Roadmap

### 📋 Phase 3 — 自动化与集成 (计划)

| 任务 | 优先级 | 说明 |
|------|:------:|------|
| 评分结果自动推送到 Google Sheet | P0 | 替代手动导出 |
| 定时任务（每周/每月自动跑分） | P1 | Cron job 或 Airflow DAG |
| 评分结果 API 化 | P2 | 供其他系统调用 |
| 邮件/企微通知 Tier 变动 | P2 | 自动告警 |

### 📋 Phase 4 — 模型优化 (计划)

| 任务 | 优先级 | 说明 |
|------|:------:|------|
| 历史趋势分析 | P1 | 看 vendor 评分随时间变化 |
| 评分窗口可配置（30/90/180天） | P1 | 不同场景不同窗口 |
| Volume-adjusted scoring | P2 | 大供应商 vs 小供应商差异化 |
| 季节性因素校正 | P3 | 节假日/旺季 volume 波动 |
| 新增 criteria 维度 | P3 | 如 Shortage (短缺) |

### 📋 Phase 5 — 系统建设 (远期)

| 任务 | 优先级 | 说明 |
|------|:------:|------|
| 数据血缘与监控 | P2 | 数据源断裂预警 |
| 权限分级（Ops/PM/管理层） | P2 | 不同角色看不同维度 |
| Seller 自服务查看评分 | P3 | Seller Portal 集成 |
| 与 PO 系统联动（自动限制下单） | P3 | D 级供应商自动暂停 |

---

## 5. 架构现状与演进方向

### 当前架构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Streamlit  │────▶│  MySQL (RDS) │     │  AWS Athena  │
│   Dashboard  │     │ yamibuy_wh   │     │ (AM mapping) │
│   (port 8502)│     │ yamibuy_po   │     └──────────────┘
└──────────────┘     │ yamibuy_im   │
                     └──────────────┘
```

### 目标架构（远期）

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Scheduler  │────▶│  Score Engine│────▶│  Result Store   │
│ (Airflow)   │     │  (Python)    │     │  (MySQL/Sheet)  │
└─────────────┘     └──────────────┘     └─────────────────┘
                           │                       │
                    ┌──────┘                       │
                    ▼                              ▼
              ┌──────────┐              ┌──────────────────┐
              │ Data Lake │              │  Dashboard (UI)  │
              │ (RDS/Ath) │              │  + API Layer     │
              └──────────┘              └──────────────────┘
                                                  │
                                                  ▼
                                        ┌──────────────────┐
                                        │  通知系统         │
                                        │ (Email/企微/SMS) │
                                        └──────────────────┘
```

---

## 6. 技术栈

| 组件 | 当前 | 计划 |
|------|------|------|
| UI | Streamlit | Streamlit + API |
| 计算引擎 | Pandas (本地) | Pandas / Spark |
| 数据库 | MySQL (RDS) | MySQL + Data Warehouse |
| 调度 | 手动 | Airflow / Cron |
| 部署 | systemd (单机) | Docker / K8s |
| 测试 | pytest + Hypothesis | + Integration Tests |
| 监控 | 无 | Grafana / CloudWatch |

---

## 7. 关键风险与待决事项

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| BPM 数据字段变更 | 评分计算失败 | 增加数据验证 + 告警 |
| MySQL 连接超时 | Dashboard 无法加载 | 连接池 + retry + 缓存 |
| Athena SSO token 过期 | Seller AM 数据获取失败 | 本地 CSV 缓存兜底 |
| 权重/阈值需更新 | 评分不反映业务需求 | 定期 review + UI 可调 |
| 数据量增长 | 查询变慢 | 分区 + 索引优化 |

---

## 8. 评分参数变更管理

**当前流程**:
1. Ops 团队在 [Google Sheet](https://docs.google.com/spreadsheets/d/1HNEzs65WF03vaEY1flrb9vOHJJHBID30QSo_-ybU6sE/edit?gid=338232131#gid=338232131) 维护 criteria 权重和阈值
2. 开发根据 Sheet 更新 `config.py` 中的默认值
3. 用户可在 Simulator UI 中临时调整参数进行模拟
4. 确认最终参数后更新代码默认值

**目标流程** (Phase 3):
1. 评分参数直接从 Google Sheet 读取（消除人工同步）
2. 参数变更自动触发重新评分
3. 评分结果自动写回 Google Sheet 指定 tab

