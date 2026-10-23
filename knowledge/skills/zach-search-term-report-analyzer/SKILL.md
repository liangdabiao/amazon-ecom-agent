---
name: zach-search-term-report-analyzer
description: |
  分析 Amazon Ads search term report（SP / SB / SD），识别候选 ASIN、报告类型、低效词、放量词、属性词、场景词和趋势变化。
  使用时机：用户上传广告搜索词报告，想判断哪些 search term 应该观察、控 bid、否定候选、继续放量，或想把搜索词里的用户需求反馈到 Listing 与投放策略时调用。
  触发词：/zach-search-term-report-analyzer
description_zh: 分析 Amazon 广告搜索词报告，识别放量词、低效词、否定候选与需求趋势
benefits-from: []
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
risk-level: medium
---

## 前置建议

本公开版 Skill 是自包含的，不依赖私有工作区文件、内部知识库、店铺配置或团队数据源。

开始执行前，建议先读取本 Skill 自带材料：

- `references/field_mapping.md` — SP / SB / SD 字段映射
- `references/decision_rules.md` — 搜索词决策规则
- `references/term_classification.md` — 品牌词、竞品词、属性词、场景词分类口径
- `references/output_template.md` — 报告与 CSV 输出模板
- `references/landable_proposal_patterns.md` — 落地型广告优化方案的 8 板块结构、徽章色规范、verdict 写法、反模式清单（用于让分析结果从"诊断"升级为"可执行"）
- `scripts/clean_search_term_report.py` — 原始报表清洗与标准化脚本
- `scripts/analyze_search_term_decisions.py` — 单 ASIN 决策分析脚本
- `scripts/fetch_listing_context.py` — 可选的 Amazon 前台 Listing 上下文抓取脚本

## 用户运营哲学硬约束（生成报告时必须默认遵守）

这套规则源自卖家运营哲学，**不是技能默认值**，但本 skill 在中文亚马逊运营场景下默认开启。覆盖产品阶段、关键词决策、措辞反模式三层：

### 1. 产品配置不预设

- 不假设产品配置（4G / WiFi / 蜂窝 / 太阳能 / 电池容量 / 防水等级 / 内存卡等任何硬件维度）
- 仅以**用户 product_notes** 和**上传搜索词报告里出现的实际线索**为准
- 缺信息写"未指定"，禁止从 ASIN 编号或品牌反推配置
- 反例：看到 "trail camera" 就推断必有 4G 蜂窝；看到 "solar" 就假设带太阳能板

### 2. 核心大词没有 ACOS 豁免

- 除非进入 `protected_keywords` 列表，否则任何关键词（含核心大词、品牌词、类目大词）都按数据判断
- 高花费低转化的核心词，照样可以建议 `lower_bid` / `pause` / 甚至 `negative`，给足证据即可
- 体量大不是保留亏损位置的理由
- 触发示例：`trail camera` 在某 ASIN 上 ACOS 125% / spend $75 / 1 单 → 直接给 `lower_bid -40%` 或位置 RoS/PP 砍到 -100%，不要因为它是品类核心词就软处理

### 3. 报告措辞反模式（禁止出现）

- 禁止写"核心词不应否定/降价"、"大词需保留"、"为了曝光不动核心词"等无条件保护语句
- 禁止把"守护"或盾牌 emoji 默认套在核心词上 — 守护属性来自 `protected_keywords` 名单，不来自词的体量
- 当 `protected_keywords` 为空时，该板块标题应明示"按数据判断，含降价 / 否定建议"，不要让用户误以为有隐式守护

### 4. 产品阶段判定 ACOS 宽严

按运营目标（goal）切换 ACOS 宽严：

| 阶段 | ACOS 姿态 |
|------|-----------|
| `profit`（盈利，**默认**） | 严：低于盈亏平衡点；高花费低转化无差别砍，不为词的体量保位 |
| `new_launch`（新品冲量） | 宽：放宽 ACOS 硬指标，重曝光/位置/CTR，允许阶段性亏损 |
| `relaunch`（老品重推） | 中：关注 CTR/CVR 拉升而非纯控 ACOS，结合 listing 评估 |
| `clearance`（清货） | 最宽：只看订单和清货速度，激进降价 + 加码高效词 |

**默认假设是 `profit`**，未明确告知阶段时按盈利做。

### 5. 始终不投 Vine 和 SBV 视频广告

- 报告里禁止建议 "开 SBV"、"加码 Vine 评论"等动作
- 这是稳定偏好，不需要用户每次重申

## 定位

广告搜索词报告不只用来找否词。它同时承担三件事：

1. 找出持续消耗预算但转化弱的词
2. 找出 CVR、ACOS 或趋势表现更好的放量候选
3. 从用户真实搜索语言里提炼属性词、场景词和 Listing 反馈线索

本 Skill 输出的是分析建议和行动候选，不会替用户直接修改广告、预算、出价或否词设置。

## 输入参数

| 参数 | 必须 | 默认值 | 说明 |
|------|------|--------|------|
| 搜索词报告文件 | 是 | - | CSV / XLSX / XLSM / XLS，优先使用 Amazon Ads 官方导出文件 |
| 品牌 | 否 | 报表字段或文件名识别 | 也可用 `--brand` 显式指定 |
| ASIN | 否 | 自动识别单一候选 | 多个候选时必须让用户选择一个 |
| 站点 | 否 | `US` | 用于可选 Listing 抓取 |
| 报告类型 | 否 | 自动识别 | SP / SB / SD；识别失败时标记 `UNKNOWN` |
| 目标 ACOS | 否 | 报表自身基准 | 用 `--target-acos 0.20` 显式传入更稳 |
| Listing 上下文 | 否 | 默认尝试 live fetch | 可用 `--listing-context-file` 提供本地标题/卖点文本 |

## 执行流程

### Step 1: 识别输入文件与分析对象

1. 读取用户上传或指定的搜索词报告。
2. 运行清洗脚本识别字段、报告类型、品牌候选和 ASIN 候选：

```bash
python3 skills/zach-search-term-report-analyzer/scripts/clean_search_term_report.py <input_file>
```

3. 如果识别到多个 ASIN，先列候选给用户选择，不要混合分析。
4. 如果品牌无法识别，允许用户用 `--brand` 显式传入；品牌只用于分组、文件命名和品牌词识别。

### Step 2: 标准化字段

按 `references/field_mapping.md` 将原始字段统一为内部字段：

- `date`
- `brand`
- `asin`
- `campaign_name`
- `ad_group_name`
- `targeting`
- `match_type`
- `search_term`
- `impressions`
- `clicks`
- `spend`
- `orders`
- `sales`
- `cvr`
- `acos`
- `roas`

缺失字段按“有就用，没有就跳过”处理；但核心字段 `search_term + clicks + spend` 缺失时必须停止。

补充：部分 Amazon 搜索词报告本身不带逐日 `date` 列，只能看到汇总窗口。这类文件不要直接判定为 BLOCKED；应优先从文件名、用户提供的日期范围或批次上下文推断窗口（如“4.20-5.20”“近 12 天”），继续做 campaign/关键词/否词/结构分析，并在数据备注中明确“趋势/21天浪费金额为按汇总窗口估算，非逐日回放”。只有在既没有 `date` 列、也无法从文件名或上下文恢复时间窗口时，才降级为 `DONE_WITH_CONCERNS` 或 `NEEDS_CONTEXT`。

### Step 3: 建立 ASIN 基准与时间窗

1. 默认以单个 ASIN 为分析单位。
2. 建立该 ASIN 近 30 天广告 CVR 基准：`orders / clicks`。
3. 分别聚合 7 / 14 / 30 天窗口的点击、花费、订单、CVR、ACOS 和趋势变化。
4. 如果用户提供 `--target-acos`，用它判断成本压力；否则使用该 ASIN 报表自身 ACOS 作参考。

### Step 4: 抓取或读取 Listing 上下文

默认行为：脚本会尝试按 ASIN 和站点访问 Amazon 前台页面，提取 title / bullets / description / breadcrumb。

稳定测试或网络受限时使用：

```bash
--skip-live-listing-fetch
--listing-context-file skills/zach-search-term-report-analyzer/examples/listing-context-sample.md
```

Listing 上下文只用于增强“相关词、属性词、场景词、弱相关词”的判断；抓取失败不能阻断基础广告分析。

### Step 5: 做搜索词决策分析

读取 `references/decision_rules.md` 和 `references/term_classification.md`，为每个 search term 输出：

- 主分类：`brand_term` / `competitor_term` / `asin_term` / `core_category_term` / `attribute_term` / `scenario_term` / `irrelevant_term` / `uncertain_term`
- 动作标签：`scale_up` / `hold_test` / `reduce_bid` / `negative_candidate` / `observe` / `listing_feedback` / `manual_review`
- 置信度：`high` / `medium` / `low`
- 解释：说明点击、花费、CVR、ACOS、趋势和 Listing 相关性如何共同支持该判断

### Step 6: 输出报告与明细

默认输出到：

```text
outputs/search-term-report-analyzer/{brand_or_unknown}/
```

脚本命令示例：

```bash
python3 skills/zach-search-term-report-analyzer/scripts/analyze_search_term_decisions.py \
  <input_file> \
  --brand ExampleBrand \
  --asin B0PUBLIC01 \
  --target-acos 0.20 \
  --listing-context-file skills/zach-search-term-report-analyzer/examples/listing-context-sample.md \
  --skip-live-listing-fetch
```

## 输出文件清单

| 文件 | 格式 | 路径 |
|------|------|------|
| 主报告 | `.md` | `outputs/search-term-report-analyzer/{brand}/{YYYY-MM-DD}_{brand}_{asin}_7-14-30天_搜索词报告分析.md` |
| 明细表 | `.csv` | `outputs/search-term-report-analyzer/{brand}/{YYYY-MM-DD}_{brand}_{asin}_7-14-30天_搜索词分析明细.csv` |
| 异常清单 | `.csv` | `outputs/search-term-report-analyzer/{brand}/{YYYY-MM-DD}_{brand}_{asin}_7-14-30天_异常清单.csv` |
| 运行摘要 | `.json` | `outputs/search-term-report-analyzer/{brand}/{YYYY-MM-DD}_{brand}_{asin}_7-14-30天_run_summary.json` |

## 风险与边界

- **本 Skill 不做**：
  - 不直接修改广告出价、预算、否词或广告结构
  - 不上传用户报表、不沉淀真实销售数据
  - 不依赖私有店铺配置或内部知识库
  - 字段不足时不强行给出 CVR / ACOS 结论
- **需要人工复核**：
  - 多个 ASIN 混在同一份报告里
  - 品牌词、竞品词或 ASIN 型搜索词策略不明确
  - Listing 抓取失败且词义相关性高度依赖产品卖点
  - 点击量低、花费低或 7 / 14 / 30 天信号互相冲突
- **risk-level = medium**：
  - 本 Skill 会给出广告动作建议，但任何出价、预算、否词执行都需要用户确认后手动完成。

## 上游 / 下游

- **上游**：
  - 用户提供的 Amazon Ads search term report
  - 可选 Listing 上下文文件
- **下游**：
  - 人工广告操作：复核否词候选、控 bid 候选、放量候选
  - Listing 优化：把属性词、场景词、需求词反馈到标题、卖点、A+ 或素材
  - **ops-hub `ad_audit` 流水线渲染**：在 `references/output_template.md §4` 的 JSON schema 基础上渲染 HTML（12 板块）+ xlsx（12 sheet）。新增字段清单：`campaign_efficiency[]` / `new_campaigns[]` / `negative_suggestions[].wasted_spend_usd` / `high_performers[].current_bid + bid_change_pct` / `action_summary[].day + eta_minutes + location_path` / `placement_diagnosis[].suggested_modifier`。

## 向后兼容 Pitfalls

- **新字段必须软降级**：渲染端用 `structured.get("new_field") or []`，历史 job 打开不崩，只是缺对应板块。新增字段时在 `output_template.md` 同步写明「字段缺失时的降级行为」。
- **bid_change_pct 必须带方向符**：`+18%` / `-15%` / `0%`，前端靠方向符换色；输出 `18%`（无符号）会被判定为 flat，色块不变。
- **efficiency_tag 值域固定**：`black_hole` / `needs_optimization` / `healthy` / `high_efficiency`，不要自造 `excellent` / `bad` 等近义词，渲染端按枚举查色表。
- **action_summary.day 可选但值域建议统一**：`Day 1` / `Day 2` / `Day 3-7` / `Day 8-14`，便于按日分组聚合；留空则归入"未排期"区块，HTML 会走 legacy flat 渲染（标题变成"建议汇总"而非"执行 Checklist"）。

## 完成后

报告完成状态：

- **DONE** — 报告、明细、异常清单和摘要均已生成
- **DONE_WITH_CONCERNS** — 已生成，但存在需人工复核的高影响项
- **BLOCKED** — 核心字段缺失、文件不可读或 ASIN 无法确定
- **NEEDS_CONTEXT** — 需要用户补充品牌、ASIN、站点、目标 ACOS 或 Listing 上下文

告知用户：

1. 分析对象：品牌、ASIN、站点、报告类型
2. 结果摘要：否词候选、控成本候选、放量候选、Listing 反馈词数量
3. 文件路径：主报告、明细表、异常清单和运行摘要
