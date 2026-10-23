---
name: amazon-asin-cosmo-rufus-audit
description: 面向新手的 Amazon ASIN 审计技能。使用 Claude Code + sorftime MCP + sif-mcp，对单个 ASIN 在 COSMO、Rufus、Listing 转化和广告投放上的表现做证据驱动分析，并输出可直接落地的改写建议与广告搭建方案。用户提到“分析这个 ASIN”“为什么这个 listing 卖不好”“做 COSMO 审计”“做 Rufus 审计”“重写标题/五点/Q&A/后台词/图片/A+”或“给广告建议”时触发；即使用户未明确说 COSMO 或 Rufus，只要目标是诊断 Amazon Listing 并改写，也优先使用本技能。
description_zh: 审计单个 ASIN 的 COSMO、Rufus 与 Listing 转化表现，产出改写与广告建议
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [amazon, asin, listing, cosmo, rufus, claude-code, mcp, conversion]
---

# Amazon ASIN COSMO + Rufus Audit

## Purpose

把单个 Amazon ASIN 的问题拆成一份可执行的审计结果，而不是泛泛点评。

本技能默认回答 4 个核心问题：
1. 当前更像是哪里失分：曝光、点击、转化，还是预期错配
2. 这些问题的证据是什么
3. 优先应该先改什么，为什么
4. 改完以后标题、Bullet、Q&A、Backend Search Terms、图片卖点、A+ 应该怎么写

## Trigger Conditions

用户出现下列表达时，优先触发本技能：
- 分析这个 ASIN
- 看下这个 listing 为什么卖不好
- 做 COSMO 审计
- 做 Rufus 审计
- 帮我重写亚马逊标题 / 五点 / 描述
- 帮我补 Q&A / Backend Search Terms / 图片卖点 / A+
- 这个产品为什么 AI 搜索不容易搜到
- 这个 listing 是曝光差还是转化差

## When Not To Use

不要硬套本技能到这些场景：
- 用户只是在问 Amazon 平台规则、代码、命令、文档用法
- 用户没有给 ASIN，也不是在讨论 ASIN 审计工作流
- 用户要的是纯广告投放执行，不需要 Listing / 评论 / 页面证据分析
- 用户只想润色一句文案，不需要完整诊断逻辑

## Required Inputs

默认输入：
- 1 个 ASIN

可选输入：
- 站点（默认 `US`）
- 用户已有证据：评论截图、旧标题、旧 Bullet、Q&A、竞品链接、竞品文案、广告表现摘要
- 用户偏好：是否要完整 10 板块报告，是否要只给改写稿

如果缺少 ASIN：
- 直接追问，不猜

## Prerequisites

### Primary workflow
本技能默认工作流是：
- **Claude Code** 作为主执行环境
- **sorftime** MCP 提供产品详情、评论、竞品关键词与竞品表达
- **sif-mcp** 提供广告、流量、趋势、经营侧证据

### What to verify first
开始前先确认：
1. `claude` 命令存在并可运行（如果你打算走 Claude Code 工作流）
2. 不要只依赖 `claude mcp list` 作为可用性结论；优先用 Hermes 原生 MCP 直连做 `initialize + list_tools` 实测
3. 目标 MCP 至少有 `sorftime`；理想状态下同时有 `sif-mcp`
4. 输出路径可写

### Important reliability note
实战中，`claude mcp list` 可能显示某个 MCP failed，但 Hermes 原生 MCP 直连仍然可成功 `initialize` 和 `list_tools`。

因此：
- **MCP 连通性判断以 Hermes 原生直连实测为准**
- `claude mcp list` 只能作为辅助参考，不能作为唯一证据
- 如果用户明确要求“不要用 Claude，只用 Hermes”，就直接改走 Hermes 原生 MCP 路径，不要继续纠结 Claude CLI 状态

如需详细排查，查看：
- `references/mcp-setup.md`

## Evidence Rules

这是本技能最重要的约束。

### Golden rules
- 先取证，再判断
- 缺失字段写 `未获取到`
- 不把猜测写成事实
- 不把行业常识写成该产品已证实信息
- 没有经营侧数据时，不把广告与业务判断写成确定结论
- 不把评论中的个例写成普遍事实，除非出现高频聚类

### Evidence labels
最终输出时，尽量显式区分：
- `[页面事实]`：标题、Bullet、属性、描述、A+、图片可读信息
- `[评论证据]`：评论 / Q&A / 用户反馈中高频出现的点
- `[经营证据]`：广告、流量、趋势、CTR、CVR、结构数据
- `[推断建议]`：基于现有证据提出的动作建议

## Degradation Strategy

如果依赖不完整，按下面降级，不要硬编。

### Case A: `sorftime` + `sif-mcp` 都可用
输出完整 10 板块审计：
- 可同时做 Listing、COSMO、Rufus、经营侧判断
- 可基于经营侧与搜索侧证据，补充可执行的广告搭建建议

### Case B: 只有 `sorftime`
允许输出：
- 页面结构问题
- 评论证据
- COSMO / Rufus 可理解性诊断
- 标题 / Bullet / Q&A / Backend Terms / 图片 / A+ 改写建议
- 如果用户强要广告建议，只能给低置信度的“测试型广告框架”，必须明确这是基于页面与语义分析的假设方案，不是经营数据验证后的定案

禁止写成定论：
- 广告结构结论
- 流量趋势结论
- CTR / CVR 的经营侧定因
- 精确竞价和放量节奏的高置信度结论

### Case C: 只有 `sif-mcp`
只能输出：
- 经营侧异常提示
- 初步广告结构建议
- 需要哪些页面证据补齐

不能直接产出高置信度 Listing 改写结论，除非用户另给页面与评论证据。
广告建议也必须明确：缺少页面与评论证据时，关键词相关性判断和转化文案承接判断都属于部分信息下的建议。

### Case D: 两个 MCP 都不可用
先尝试 **Amazon 页面直取证**，不要立刻停止：
- 用浏览器直接打开 `https://www.amazon.com/dp/<ASIN>` 抓取标题、价格、评分、评论量、类目路径、Bullet、产品详情字段
- 用页面脚本读取评论首屏、A+、图片 URL、PDP facts
- 用视觉工具分析主图与 A+ 图中的真实可见文案、参数、卖点布局
- 再用 Amazon 搜索结果页对核心查询做轻量竞品对比（价格、评分、评论量、标题结构、是否进前排）

如果 Amazon 直取证也失败，再要求用户补充至少以下内容：
- ASIN
- 当前标题
- 5 条 Bullet 或产品描述
- 至少 10 条评论 / 差评摘要，或截图
- 竞品 1-3 个链接或竞品文案

此时只能做“人工证据版审计”，并明确标注不是完整 MCP 审计。

### Amazon 页面直取证注意事项
- Amazon 容易触发 503 / continue shopping / bot challenge；优先直接访问 `/dp/<ASIN>`，必要时点击 `Continue shopping`
- 搜索页比详情页更容易触发风控；需要竞品时先少量查询，避免反复翻页
- 页面文本快照常会缺 A+ 细节，优先配合 DOM 抽取和图片视觉分析
- 如果 A+ 图上出现与类目不一致的词（例如把 trail camera 写成 action camera），应列为高优先级冲突证据
- 如果页面参数存在冲突（如 WiFi 距离 45ft/65ft、trigger speed 与 shutter speed 混写），应在 COSMO/Rufus 风险里单独指出

## Execution Flow

### Step 1: Confirm scope
确认：
- ASIN
- 站点（未给则默认 `US`）
- 用户想要完整报告，还是只要改写建议

### Step 2: Check capability
优先检查：
- Claude Code 是否可用
- `claude mcp list` 是否显示 `sorftime` / `sif-mcp`
- 输出路径是否可写

### Step 3: Gather evidence
优先收集：
1. 产品基础信息
2. 当前标题、Bullet、属性、描述
3. 主图 / 辅图可读信息
4. 评论与差评高频问题
5. Q&A / 用户典型疑问
6. 竞品关键词或竞品表达
7. 广告、流量、趋势、经营侧数据（如果 `sif-mcp` 可用）

### Step 4: Diagnose the problem type first
不要一上来就整份重写。先判断当前更像哪一类：
- **曝光问题**：核心词错、类型词偏、属性缺失、语义理解失败
- **点击问题**：可被搜到，但主图、标题、差异化不够让人点
- **转化问题**：用户进页后，决策信息缺失或顾虑没有被回应
- **预期错配问题**：买前承诺与买后体验不一致，容易误购、退货、差评

### Step 5: Score on 7 dimensions
每次至少围绕这 7 维打分或判断：
1. `语义检索匹配度`
2. `查询属性覆盖度`
3. `COSMO 知识图谱对齐度`
4. `隐式查询解析友好度`
5. `Rufus 因果链完整度`
6. `用户行为信号质量`
7. `可解释比较生成能力`

### Step 6: Prioritize actions
优先级永远按：
- `纠错 > 补齐 > 强化 > 美化`

优先级定义：
- `P0`：误购、退货、差评、属性过滤失败、Rufus 回答错误、明显合规风险
- `P1`：显著影响 CTR / CVR 的表达与信息缺失
- `P2`：视觉增强、A+ 扩展、表达润色

### Step 7: Produce final deliverables
根据用户要求，输出：
- 完整报告
- 或精简版诊断 + 改写稿

如果 `sif-mcp` 提供了足够经营侧数据，还应补充“广告搭建建议”，至少回答：
- 应搭建哪些广告活动
- 每类活动应投哪些关键词 / 商品定向 / 人群意图
- 起始竞价建议是多少
- 使用什么竞价策略
- 哪些词应该否定，哪些词应观察
- 预算如何按冷启动 / 放量 / 控 ACOS 三种目标分配

如需标准格式，参考：
- `templates/report-template.md`
- `templates/rewrite-template.md`

## Standard Output Structure

完整报告按以下 11 个板块输出：
1. 产品概览
2. 算法评分卡
3. 语义检索盲区分析
4. COSMO 节点诊断
5. Rufus 问答能力测试
6. 用户行为信号诊断
7. 竞品差异化可提取性
8. 改进优先级方案
9. 广告搭建建议
10. 优化后文案
11. 图片卖点与 A+ 创意方案


如果用户只要简版交付，也不要跳过判断逻辑，只压缩篇幅。

## Advertising Recommendation Rules

只有在拿到足够经营侧证据时，才把广告建议写成“可执行搭建方案”。

### Evidence needed for high-confidence ad planning
优先参考这些数据：
- 已有广告活动结构
- 搜索词表现
- CTR / CVR / CPC / ACOS / ROAS
- 曝光、点击、订单、花费分布
- 高转化词、烧钱词、低相关词、无转化词
- 竞品 ASIN 或竞品词表现
- 不同 match type 的表现差异

### If evidence is incomplete
- 可以给测试型广告框架
- 但要明确哪些竞价、预算、关键词分组是“假设起盘”，哪些是“数据验证后建议”
- 不要把估算 CPC 说成平台实时建议价

### Minimum structure for ad recommendations
广告建议至少包含：
1. `广告目标`：冷启动 / 稳定放量 / 控 ACOS / 清库存 / 防守品牌词
2. `活动类型`：SP 自动、SP 手动、SB、SB Video、SD（按证据决定是否需要）
3. `活动拆分逻辑`：按词性、意图、品牌/泛词、竞品/类目、match type 拆开
4. `关键词或定向清单`：每组至少给出建议投放对象
5. `起始竞价`：写清楚建议区间或基准计算逻辑
6. `竞价策略`：Dynamic bids down only / up and down / fixed bids
7. `预算建议`：按活动类型给出日预算或预算分配思路
8. `否定词策略`：哪些词要否，哪些词先观察
9. `观察周期与调价规则`：多少点击、多少花费、多少天后调整

### Campaign design defaults
如果没有更强证据，优先采用以下拆分方式：
- `SP Auto`：用于挖词与发现 ASIN 定向机会
- `SP Manual - Exact`：承接高相关高意图核心词
- `SP Manual - Phrase/Broad`：承接扩量与语义变体
- `SP Product Targeting`：打竞品 ASIN、替代品 ASIN、同价位段竞品
- `SB / SB Video`：当品牌词、品类教育词、视觉解释价值较高时加入
- `SD`：仅在有再营销、竞品拦截或受众证据时建议加入

### Bid guidance rules
竞价建议不要凭空拍脑袋，优先这样写：
- 若 MCP 提供建议竞价区间或历史 CPC：以其为基准
- 若已有历史 CPC：
  - `核心高转化词`：可从历史平均 CPC 的 `0.9x-1.15x` 起盘
  - `测试词 / 扩量词`：可从历史平均 CPC 的 `0.7x-0.9x` 起盘
  - `竞品词 / 高风险词`：可从历史平均 CPC 的 `0.6x-0.85x` 起盘
- 若没有历史 CPC，只能给区间型建议，并标注为测试起盘价

### Bidding strategy rules
默认判断逻辑：
- `核心高意图 Exact`：优先 `dynamic bids - up and down` 或 `down only`，取决于 ACOS 目标和转化稳定性
- `Broad / Phrase 扩量`：优先 `dynamic bids - down only`
- `Auto 挖词`：优先 `dynamic bids - down only`
- `高不确定性测试活动`：优先 `fixed bids` 或 `down only`

### Negative keyword rules
至少把词分成三类：
- `立即否定`：明显错误流量、错误产品类型词、极低相关词
- `观察后否定`：高花费低转化词、点击多无单词
- `保留测试`：CTR 好但样本不足、CVR 尚未稳定的词

### Ad output style
广告建议必须写到动作级，避免空话，比如不要只写：
- “开自动广告”
- “提高竞价”

而要写成：
- 建 1 个 SP Auto 挖词活动，拆 4 个 targeting group，日预算 xx，竞价策略 xx
- 建 1 个 SP Manual Exact 活动，放 8-15 个核心词，竞价区间 xx-xx
- 将词 A、B、C 设为否定词，将词 D、E 保留观察 5-7 天

## Rewrite Rules

### Title
标题优先顺序：
1. 品牌与核心产品词
2. 用户真实会搜的主意图词
3. 关键差异化或关键规格
4. 高价值场景或适用对象
5. 必要硬属性

不要写成关键词垃圾桶。

### Bullet
5 条 Bullet 尽量各司其职：
1. 核心痛点 / 主差异化
2. 使用场景
3. 硬参数和可验证事实
4. 目标人群 / 边界条件
5. 顾虑与信任问题

尽量采用：`痛点 → 机制/事实 → 结果 → 边界条件`

### Q&A
优先覆盖：
- 这是什么
- 适合谁
- 怎么选
- 需要注意什么
- 不适合什么情况
- 评论里最常见的问题

### Backend Search Terms
- 放同义词、补充词、场景词、互补词
- 不重复标题和 Bullet 已覆盖的词
- 不堆砌，不重复，不塞无关词
- 会引来错误流量的词，即使有搜索量也不要保留

## Image & A+ Rules

图片与 A+ 不是重复标题和 Bullet，而是补充用户最需要被视觉解释的信息。

必须至少覆盖：
- `主图优化建议`：3-5 条
- `辅图卖点拆解`：至少 6 张
- `应用场景图建议`：至少 3 个
- `A+ 页面方案`：至少 5 个模块
- `合规提醒`：至少 5 条

## Compliance Red Flags

发现以下问题时，优先列为 `P0`：
1. 标题、Bullet、属性、图片语义互相冲突
2. 错误产品类型词
3. 无法证实的绝对化宣传词
4. 关键购买决策信息缺失
5. 评论高频抱怨未被页面回应
6. 属性字段空缺，导致 AI 过滤不可见
7. 关键词堆砌、机械 SEO、硬塞关系词
8. 用户最关心的问题只能靠猜

重写时不要保留：
- 无法证实的极限承诺
- 医疗疗效、绝对化承诺、未经证实的比较结论
- 未经授权的品牌侵权表达
- 主图中的促销语、价格、赠品、徽章要求
- 攻击性竞品表达

## Suggested Beginner Prompt Patterns

### Minimal
`分析 B0XXXXXXXXX`

### Evidence-first
`请基于真实证据，分析 B0XXXXXXXXX，站点 US`

### Full audit
`请基于真实证据，分析 B0XXXXXXXXX，输出完整 11 板块 COSMO + Rufus + 广告建议报告；不要猜测，缺失字段标注未获取到`

### Audit + rewrite
`请基于真实证据，分析 B0XXXXXXXXX，并给我优化后的标题、5 条 Bullet、Backend Search Terms、6 条 Q&A、图片卖点和 A+ 方案`

## Output Style

- 简洁、专业、可执行
- 结论尽量绑定证据
- 建议必须具体到动作
- 信息不足时直接指出盲区
- 用户明确要交付物时，优先给结果，不讲长篇空话

## Final Principle

本技能的目标不是“显得懂 Amazon”，而是：
- 让 Amazon 搜索、COSMO、Rufus 更容易理解产品
- 让用户更快看懂为什么该买
- 让运营团队直接拿去改 Listing 和图片

优先输出：
- 可验证的诊断
- 有顺序的优先级
- 可直接落地的改写稿
而不是空泛分析。
