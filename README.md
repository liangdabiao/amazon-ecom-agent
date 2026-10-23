# ecom-agent · 你自己的亚马逊运营 AI 助手

一个跑在**你自己电脑上**的亚马逊运营 AI 助手：打开浏览器、像聊天一样下任务，
它自己调工具查数据、写文案、做图、诊断广告，把结果直接交给你。

```
你：「调研一下 yoga mat 在美国市场的机会」
它：自动查搜索量/趋势/竞品/类目数据 → 写出完整调研报告

你：「帮我写一款保温杯的 Listing」
它：按亚马逊最新规则生成 5 个标题 + 五点描述 + 搜索词，附合规自查

你：「data/reports 里这份广告报表帮我诊断一下」
它：自己解析报表 → 告诉你哪些词在烧钱、哪些该加价、每一步怎么操作
```

**基于 [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) 构建**，
DeepSeek / GLM / Kimi / OpenAI 等任意模型都能用，改一行配置就切换。
全部 ~2600 行代码，没有账号体系、没有审批流程——装好就能用。

---

## 它能干什么

| 你说 | 它做 | 背后的能力 |
|---|---|---|
| 「调研 XX 关键词」 | 一键采集 10 项市场数据，产出完整调研报告 | Sorftime / 卖家精灵 数据源 |
| 「分析这个竞品 ASIN」 | 商品概况、销量趋势、流量词结构、评论洞察 | 同上 |
| 「采集这个商品的页面」 | 抓标题、五点描述、全套主图到本地 | 本机直连 Amazon（带反爬） |
| 「写 Listing 文案」 | 5 标题 + Product Highlights + 2 组五点 + 搜索词 | 内置亚马逊 2026-07 新政规则 |
| 「生成一张场景主图」 | AI 生图，产品长相和参考图严格一致 | gpt-image 生图链路 |
| 「做一套 7 张主图 + A+」 | 按叙事结构规划分镜，整套顺序生成 | 整套图工作流（保参考图产品一致） |
| 「把图翻译成德语」 | 版式产品完全不变，只换图上文字 | 一套图铺多站点 |
| 「诊断广告报表」 | 哪些词烧钱无单、哪些该提价、逐条执行清单 | 把 xlsx/csv 报表放 `data/reports/` 即可 |
| 「查一下店铺上月的销量」 | 读领星 ERP 真实经营数据 | 领星官方 OpenAPI（**只读**） |
| 「FBA 费用怎么算」 | 查内置知识库回答，注明来源文档 | **内置 86 篇亚马逊运营知识**（费用/政策/FBA/广告/税务…） |

## 快速开始（3 步）

**前提**：装好 Python 3.10+（Windows / macOS / Linux 都行），会开命令行。

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 配置：复制 .env.example 为 .env，填一个模型 API Key
#    （DeepSeek / GLM / Kimi / OpenAI 任一，去各家官网申请，几分钱能聊很久）
cp .env.example .env

# 3. 启动
python -m uvicorn server.main:app --port 8100
```

浏览器打开 **http://127.0.0.1:8100**，开始下任务。

喜欢命令行的话：

```bash
python cli.py "调研 yoga mat 的 US 市场"   # 一句话任务
python cli.py                              # 或进入连续对话模式
```

## 配置说明（.env）

只有一个配置文件，**要什么配什么，不用的留空即可**：

| 键 | 干什么用 | 不配会怎样 |
|---|---|---|
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | **必填**。对话模型 | 不配没法用 |
| `SORFTIME_KEY` | 市场调研数据（[sorftime.com](https://www.sorftime.com) 申请） | 市场调研类工具不可用 |
| `SELLERSPRITE_KEY` | 备用数据源（卖家精灵） | 和上面二选一即可，自动切换 |
| `IMAGE_BASE_URL` / `IMAGE_API_KEY` | AI 生图/图片翻译（需有 gpt-image 权限的中转） | 生图、翻译工具不可用，其余正常 |
| `LINGXING_HOST` / `LINGXING_APP_ID` / `LINGXING_APP_SECRET` | 领星 ERP 查店铺真实数据 | 领星工具不可用，其余正常 |

换模型 = 改三行。比如换 GLM：`LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4`、
`LLM_MODEL=glm-4-plus`、填上智谱的 key。

## 项目结构

```
server/
  agent.py      ← Agent 定义，就 60 行
  main.py       ← 网页服务（一个聊天接口）
  tools/        ← agent 的 14 个工具（查数据/采集/生图/读报表/查领星）
  legacy/       ← 核心资产：数据源对接、页面采集、生图链路（带大量实战注释）
prompts/
  system.md     ← 运营 know-how 全在这里，想调教它就改这个文件
web/index.html  ← 聊天界面（单文件，无外部依赖）
cli.py          ← 终端入口
knowledge/      ← 内置 86 篇亚马逊运营知识 + 11 套实战技能方法论（ASIN 审计、
                  广告诊断、Listing 创意、市调报告模板…），可继续放自己的
data/           ← 运行数据：生成的图片、你放的广告报表、对话记录
```

## 常见问题

**Q：模型 Key 去哪申请？**
DeepSeek（[platform.deepseek.com](https://platform.deepseek.com)）、智谱 GLM、Kimi、OpenAI
都可以，任何"OpenAI 兼容"的端点都行。填 `base_url` + `key` + 模型名三个值。

**Q：市场调研报"Sorftime Key 未配置"？**
在 .env 里填 `SORFTIME_KEY`，或者填 `SELLERSPRITE_KEY` 用卖家精灵。只用聊天、写文案、
生图的话不配也能用。

**Q：生成的图在哪？**
`data/images/` 目录，聊天回复里也能直接点开。

**Q：广告报表怎么给它？**
把亚马逊后台下载的搜索词报表（xlsx/csv）放进 `data/reports/`，然后跟它说
"诊断一下报表"。文件名不确定就先问它"有哪些报表"。

**Q：它会乱改我的广告/店铺吗？**
不会。它对领星是**硬只读**（代码层面写操作直接被拒），对广告只出诊断建议，
执行永远由你自己在后台完成。

**Q：数据会传到别人服务器吗？**
对话和文件都在本机；调外部服务只有三类：你配的模型 API、数据源 API、生图中转。
密钥只存在你自己的 `.env` 里。

## 来源与致谢

本项目的核心资产（数据源对接、Amazon 页面采集、生图链路、Listing 规则与广告方法论）
平移自同作者的 [IvyeaOps](https://github.com/Hector-xue/IvyeaOps)——一个功能完整但更重的
自托管运营工作台。如果你想要完整版（多用户、审批流、Skill 工坊、知识库治理等），去用它。

## 许可证

AGPL-3.0（沿用上游 IvyeaOps 的许可证）。
