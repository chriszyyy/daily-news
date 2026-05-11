---
name: daily-briefing
description: 每日中国股票交易情报简报的完整工作流。当用户说"做今日简报"、"daily news"、"/loop"调用、或要求生成 reports/YYYY-MM-DD.md 时使用。17 步编排：context loading → data collection → signal pipeline → audit。
---

# Daily Briefing Workflow

本 skill 是 daily-news 项目的主流程编排器。所有具体方法论封装在子 skill 中,本文件只编排顺序与 gate。

## Contract

- **Triggers**: "做今日简报" / "daily news" / `/loop` / 生成 `reports/YYYY-MM-DD.md`
- **Inputs**: 当前日期(BJT) + knowledge/* + decisions/positions.md + 最近 2-3 份 daily decision logs
- **Outputs**: `reports/YYYY-MM-DD.md` + `decisions/YYYY-MM-DD.md`(含 audit) + 状态变化时更新 `knowledge/*` 和 `research/INDEX.md`
- **Calls**: `tool-fallback`(失败时)、`bottleneck-analysis`(P3.1)、`signal-generation`(P3.2 每条信号)、`fundamental-deepdive`(P3.3 每候选)、`data-validation`(P3.4)、`discover-new-stocks`(P3.5)、`briefing-audit`(P3.7 强制最后一步)
- **Called by**: 用户

## ⚠️ 强制执行规则

1. **17 步全跑**,假期/休市也不跳过(用最新可用数据)
2. **开始前用 TodoWrite 构建 17 步清单**,逐步标 completed
3. **🔴 工具问题不终止任务** — 任何失败立即调 `tool-fallback` skill
4. **市场状态验证**:`Bash date` 确认 BJT,Yahoo `marketState` 字段交叉验证
5. **任何信号必走 `signal-generation`** — 4 道闸全过才入库
6. **末尾必调 `briefing-audit`** — 防止 skill 被软跳过

## Phase 1: Context Loading

### P1.1 [Data] Load knowledge base
读:
- `knowledge/context.md` / `ai-landscape.md` / `watchlist-sectors.md`
- `research/INDEX.md`
> 注:方法论文档(`bottleneck-framework.md` / `tool-fallbacks.md`)已下沉到 skill,**不再单独读**——需要时调对应 skill。

### P1.2 [Data] Load positions
读 `decisions/positions.md` + 最近 2-3 份 `decisions/YYYY-MM-DD.md`。

### P1.3 [Output] Identify follow-ups
列出:
- 需价格更新的持仓
- 需止损/止盈检查的持仓
- 研究中/观察中/已建仓课题候选

## Phase 2: Data Collection

### P2.1 [Data] Verify BJT date and market state
`Bash date` → 确认日期 + Yahoo `marketState` 字段 → 判断 REGULAR/CLOSED/POSTPOST/PREPRE。

### P2.2 [Data] Extract prices
- Yahoo: 指数 + 商品 + 外汇 + 持仓股 + 课题候选股
- Alpha Vantage: 美股技术指标 + sentiment

### P2.3 [Gate] Check positions vs stop/target
对比当前价 vs 止损/止盈,flag 触发项 → 进入 P3.2 的卖出/减仓信号通道。

### P2.4 [Data] News search (中英双语)
启动 background news subagent,跑最小查询集:

| # | English | Chinese | Covers |
|---|---------|---------|--------|
| 1 | `US economy Federal Reserve today` | — | Fed/US 宏观 |
| 2 | `China economy trade PBOC today` | `中国经济 央行 贸易 今日` | China 宏观 |
| 3 | `US China relations sanctions tariffs` | `中美关系 制裁 关税` | 地缘 |
| 4 | `AI artificial intelligence chips breakthrough` | `人工智能 大模型 AI芯片 算力` | AI |
| 5 | `China stock market A-shares Hong Kong` | `A股 港股 行情` | 中国市场 |
| 6 | `oil gold commodities prices today` | — | 商品 |
| 7 | — | `液冷 变压器 光模块 PCB 先进封装 AI算力` | A股供应链 |
| 8 | `AI data center power cooling storage bottleneck` | — | AI 瓶颈 |
| 9 | — | `低估值 被忽视 AI算力 供应链 港股折价` | 低估/被忽视 |

### P2.5 [Data] Pull macro data
FRED 拉新发布的美国宏观数据(CPI/GDP/失业/NFP/利率/零售)。

## Phase 3: Analysis & Output

### P3.1 [Skill] Bottleneck supply chain scan
调 `bottleneck-analysis` skill:
- 瓶颈轮动:GPU → 存储/HBM → 电力/变压器 → 液冷 → PCB → 封装
- 52-week 涨幅找滞涨段
- 海外龙头爆发 → 扫 A 股映射

### P3.2 [Skill ⭐] Signal generation pipeline
**每条信号必走** `signal-generation` skill 的 4 道闸:
- Gate 1 技术面(MA/RSI/MACD/%B)
- Gate 2 Kelly 仓位
- Gate 3 瓶颈硬约束(必调 bottleneck-analysis 子调用)
- Gate 4 Devil's Advocate 反方观点

包含:
- 新信号
- 此前所有 open signal 的跟进(状态/价格更新)
- 持仓的卖出/减仓决策

### P3.3 [Skill] Fundamental deepdive(候选标的)
对**新进入候选**(Kelly 为正且通过 4 道闸)调 `fundamental-deepdive` skill 完成 6 维度+G 框架。

### P3.4 [Skill] Data validation(背景)
调 `data-validation` skill,启 `run_in_background: true` 验证 subagent。在 P3.7 audit 前必须 review 结果。

### P3.5 [Skill] Discover new stocks
调 `discover-new-stocks` skill:
- 任何信号股价 >¥40 或 52w >200% → 强制找替代
- 每次至少新增 3-5 个未跟踪标的入 watchlist

### P3.6 [Output] Write report + decisions + knowledge updates

写入:
- `reports/YYYY-MM-DD.md`(中文,格式见 CLAUDE.md "Report Format")
- `decisions/YYYY-MM-DD.md`(含每条信号的 4-Gate 输出)
- `decisions/positions.md`(更新)
- `research/INDEX.md`(课题进展)
- 状态变化才更新 `knowledge/context.md` / `ai-landscape.md` / `watchlist-sectors.md`(触发条件见 CLAUDE.md "Knowledge Update Triggers")
- 流程缺口写入 `knowledge/prompt-evolution.md`

### P3.7 [Audit ⭐ 强制] Briefing audit
**强制最后一步**。调 `briefing-audit` skill:
- 17 步是否全跑(读 TodoWrite)
- 4 道闸是否全过(每条信号)
- knowledge/ 更新是否被遗漏
- 数据警示/fallback 是否记录

Audit 报告 append 到 `decisions/YYYY-MM-DD.md` 末尾。**FAIL 项必须修正后才结束**。

## Data Freshness Rules(嵌入式)

- 用户 UTC+8;A股 9:30-11:30+13:00-15:00 BJT;港股 9:30-12:00+13:00-16:00;美股 21:30-04:00 (DST)
- Yahoo `marketState` 是权威:REGULAR=交易,POSTPOST=已收,PREPRE/PRE=未开(日内字段为 stale)
- 报告表格必标时间戳

## 与子 skill 的契约关系

```
daily-briefing
├── tool-fallback         (P*.* 失败时)
├── bottleneck-analysis   (P3.1)
├── signal-generation     (P3.2 — 内部又调 bottleneck-analysis + tool-fallback)
├── fundamental-deepdive  (P3.3 — 内部又调 bottleneck-analysis)
├── data-validation       (P3.4 background)
├── discover-new-stocks   (P3.5 — 内部又调 bottleneck-analysis)
└── briefing-audit        (P3.7 强制)
```
