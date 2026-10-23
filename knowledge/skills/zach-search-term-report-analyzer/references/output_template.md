# 输出模板

本文件定义 `zach-search-term-report-analyzer` 的标准输出结构。

默认输出 4 类结果：

1. Markdown 主报告
2. CSV / 表格明细
3. 异常清单
4. 行动建议摘要

---

## 1. Markdown 主报告模板

```markdown
# 亚马逊搜索词报告分析

## 分析对象
- 品牌：
- ASIN：
- 报告类型：SP / SB / SD
- 分析窗口：7 / 14 / 30 天
- 数据来源：

## 核心结论摘要
- 否词候选：
- 潜力属性词 / 场景词：
- 需继续观察的词：
- 主要趋势变化：

## 否词候选
| 搜索词 | 主要原因 | 核心数据 | 建议动作 |
|--------|----------|----------|----------|

## 放量候选
| 搜索词 | 主要原因 | 核心数据 | 建议动作 |
|--------|----------|----------|----------|

## 属性词 / 场景词洞察
| 搜索词 | 分类 | 趋势 | 广告建议 | Listing建议 |
|--------|------|------|----------|-------------|

## 需继续观察 / 人工复核
| 搜索词 | 原因 | 建议 |
|--------|------|------|

## 7 / 14 / 30 天趋势变化
| 搜索词 | 7天 | 14天 | 30天 | 趋势判断 |
|--------|-----|------|------|----------|

## 行动建议
### 立即处理
- 

### 建议测试
- 

### 持续观察
- 

### 反馈到 Listing / 投放策略
- 
```

---

## 2. 明细表建议字段

建议输出以下列：

- `search_term`
- `term_category`
- `decision_tag`
- `match_type`
- `clicks`
- `spend`
- `orders`
- `cvr`
- `acos`
- `7d_clicks`
- `7d_cvr`
- `14d_cvr`
- `30d_cvr`
- `trend_flag`
- `notes`

---

## 3. 异常清单建议字段

建议输出以下列：

- `search_term`
- `issue_type`
- `reason`
- `priority`
- `suggested_action`

其中 `issue_type` 可选：

- `negative_candidate`
- `high_spend_low_return`
- `trend_worsening`
- `manual_review`

---

## 4. 落地型 JSON 结构（ops-hub 广告诊断渲染用）

当配合 ops-hub `ad_audit` 流水线使用时，除上述 markdown 外还需输出以下 JSON 字段（见 `landable_proposal_patterns.md`）：

```jsonc
{
  "overview": { "...": "", "one_line_verdict": "" },

  // NEW · Campaign 级效率对比（先看盘再看词）
  "campaign_efficiency": [
    {
      "campaign_name": "SP-Core-Exact",
      "type": "SP-Exact",
      "spend": 129.52, "spend_share": "65%",
      "orders": 11, "order_share": "22%",
      "cost_per_order": "$11.78", "acos": "43%",
      "efficiency_tag": "black_hole|needs_optimization|healthy|high_efficiency",
      "verdict": "65% 预算产 22% 单量 = 效率黑洞"
    }
  ],

  // 守护词：ops-hub 会置顶渲染，带 🛡️ 徽章
  "protected_keywords_status": [ { "keyword": "", "status": "good|warn|bad", "note": "" } ],

  "high_performers": [
    {
      "keyword": "", "match_type": "",
      "current_bid": "$2.96", "suggested_bid": "$3.50",
      "bid_change_pct": "+18%",  // 格式: +X% / -X% / 0%
      "action": "boost|watch", "reason": ""
    }
  ],

  "low_performers": [ { "action": "cut|pause|lower_bid", "...": "" } ],

  "negative_suggestions": [
    {
      "term": "", "type": "immediate|watch", "reason": "",
      "wasted_spend_usd": 18.40,  // NEW · 过去 N 天浪费金额
      "window_days": 21
    }
  ],
  "negative_wasted_total_usd": 67.30,  // NEW · 否词预计直接省金额

  // NEW · 新 Campaign 抄作业版
  "new_campaigns": [
    {
      "name": "SP-Exact-Core-ToS",
      "type": "SP", "match_type": "exact",
      "daily_budget_usd": 30, "bid_strategy": "down_only",
      "placement_modifiers": { "top_of_search": "+50%", "rest_of_search": "0%", "product_pages": "0%" },
      "keywords_with_bid": [ { "keyword": "trail camera", "bid_usd": 2.50 } ],
      "sync_actions": [ "SP-Auto 里这些词加否定精准" ],
      "verdict": "核心词独立打搜索首页，防止自动互抢"
    }
  ],

  "placement_diagnosis": [ { "placement": "", "suggested_modifier": "+150%", "action": "" } ],

  "action_summary": [
    {
      "level": "P0|P1|P2",
      "day": "Day 1|Day 2|Day 3-7|Day 8-14",  // NEW · 时间线分组
      "eta_minutes": 10,                        // NEW · 预估耗时
      "location_path": "广告活动 → SP-Core → 否定关键词",  // NEW · 操作路径
      "action": "", "evidence": "", "expected_impact": ""
    }
  ],

  "data_notes": "",
  "meta": { "analyzed_at": "", "row_count": 0, "threshold_posture": "" }
}
```

**字段级说明**：

- `efficiency_tag` 四档：`black_hole`（效率黑洞，底色红）/ `needs_optimization`（需优化，黄）/ `healthy`（健康，绿）/ `high_efficiency`（高效，蓝）
- `bid_change_pct` 必须显式写方向符 `+18%` / `-15%` / `0%`，前端按方向换色
- `wasted_spend_usd` 可留 0（未计算），留空则不展示浪费金额列
- `day` 用于时间线分组；未分组的动作归入"未排期"
- `location_path` 类似面包屑，帮助运营一眼定位 Seller Central 操作位置

**软兼容**：所有新字段用 `.get() or []` 降级，历史 job 打开不崩，只是缺少对应板块渲染。

---

## 5. 文件命名规则

默认文件名遵循：

- `YYYY-MM-DD_{品牌}_{ASIN}_{时间窗}_搜索词报告分析.md`
- `YYYY-MM-DD_{品牌}_{ASIN}_{时间窗}_搜索词分析明细.csv`
- `YYYY-MM-DD_{品牌}_{ASIN}_{时间窗}_异常清单.csv`

---

## 5. 完成信号模板

终端结束语默认包含 3 句话：

1. `已完成 {品牌} / {ASIN} / {报告类型} 的搜索词报告分析。`
2. `否词候选 {N} 个，潜力属性词/场景词 {M} 个，需观察词 {K} 个。`
3. `报告已保存到 {path}。`
