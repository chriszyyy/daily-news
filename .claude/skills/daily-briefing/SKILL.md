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
7. **🚫 NO GUESSING** — 见下方"🚫 NO GUESSING"
8. **🗂 SSOT** — 见下方"🗂 SSOT"
9. **💰 P&L 术语** — 见下方"💰 P&L 术语"

## 🚫 NO GUESSING — 数据准确性硬约束

**所有数字(价格 / 持仓 / 现金 / 财报 / 涨跌幅 / 仓位占比)必须来自实测或用户确认,严禁猜测或推算。**

### 强制规则
1. **价格 / 财报 / 估值** — Yahoo Finance MCP 直接拉,标注时间戳;不能用"估"、"约"、"差不多"
2. **持仓 / 现金 / 成本价** — 必须从 `decisions/positions.md` 读取,或用户主动提供;**绝不基于历史推算当前余额**
3. **涨跌幅 / 浮盈** — 必须 (现价 - 成本价) / 成本价 实算;不可以"看起来差不多"
4. **遇到不一致** — 立即 AskUserQuestion 或直接问;**不要猜测哪个对**
5. **历史数据可能过时** — 所有从历史文件读出的数字默认"待验证",用户确认前不当真

### 反模式(严禁)
- ❌ "估算约 57%" / "可能在 ¥10-15 之间" / "黄金大概 ¥83K"
- ❌ 基于历史推算当前余额("之前透支 ¥1,145 → 现在应该是 ¥X")
- ❌ 警告"可能 stale"但仍基于 stale 下结论 — 警告不等于免责

## 🗂 SSOT — 单一事实源(防文档漂移)

**核心**:**每个数据点只在一个文件中维护**,其他文件**禁止重复存储**,只能引用。

### 数据归属表

| 数据类型 | 唯一源 | 其他文件 |
|---|---|---|
| 持仓量/成本价/当前价/浮盈 | `decisions/positions.md` | 只写"详见 positions.md",严禁复制价格 |
| 现金余额 | `decisions/positions.md` 头部 | 同上 |
| 每日操作信号 + 4 道闸输出 | `decisions/YYYY-MM-DD.md` | reports/ 只写摘要,链接到决策日志 |
| 课题进展 + 候选标的逻辑 | `research/topicXX.md` | INDEX.md 只列状态行 |
| 板块逻辑 / 子链分类 | `knowledge/watchlist-sectors.md` | research/ 只引用 |
| AI 产业图谱 | `knowledge/ai-landscape.md` | 同上 |
| 宏观状态 / 关键催化 | `knowledge/context.md` | reports/ 引用日期戳 |
| 方法论 / 流程 | `.claude/skills/*` | CLAUDE.md 只放索引 |

### 价格写入硬规则
任何文件写持仓股票"当前价"或"涨跌%" → 必须满足 1 个:
1. 该文件本身就是 source of truth(positions.md 或当日 decisions/YYYY-MM-DD.md)
2. **明确标注时间戳**:`¥X.XX (5/12 收 POSTPOST 实测)`
3. 否则只写 `[价见 positions.md]` 或不写

### 反模式(严禁)
- ❌ `watchlist-sectors.md` 写"国茂 ¥17.72 已建仓" — 价格会过期且不会自动更新
- ❌ `research/INDEX.md` 写当前价无日期戳

### 强制点
- daily-briefing P1.1 加载 knowledge/* 时**只读逻辑/分类,价格全部去 positions.md 取**
- briefing-audit Check 6 grep 全文件价格与 positions.md 比对

**Why**: 2026-05-12 国茂案例,同一标的价格散落 8 个文件,信号生成可能基于错误数据。

## 💰 P&L 术语严格区分(防"累计 vs 当日"混淆)

**触发**:任何写浮盈/盈亏/贡献的语境。

| 术语 | 公式 | 含义 |
|---|---|---|
| **累计浮盈** | (今日收 - **成本价**) × 持股 | 从开仓到现在赚多少(含历史) |
| **当日浮盈变化** | (今日收 - **昨日收**) × 持股 | 今天一天市值变多少 |
| **已实现** | (卖出价 - 成本价) × 卖出数 | 卖出锁定的盈亏 |

### 反模式(严禁)
- ❌ 写"当日贡献 +¥X" 但实际公式是"累计浮盈 + 已实现"
- ❌ 把"已实现"塞进"浮盈"里

### 正确做法
- ✅ 标题写"截至 5/12 收盘 累计浮盈"或"5/12 当日净赚"二选一,不能模糊
- ✅ 用户问"今天赚多少" → **默认给当日浮盈变化**,顺带提累计
- ✅ 持仓总览段:同时给"累计浮盈"和"当日浮盈变化"两栏

**Why**: 2026-05-12 案例,报告写"当日总贡献 +¥1,314"实际是累计 +¥1,070 + 已实现 +¥244,真正当天净赚仅 +¥491。

## 🕐 数据新鲜度强制门(每次响应前必检)

**触发**:每次涉及"持仓 / 价格 / 涨跌幅 / 信号"的响应前。

### 必检 3 步
1. **`Bash date`** 拿当前 BJT 时间(每次响应必跑,不能凭印象)
2. **对比上次拉数据的时间戳** — 若超过 30 分钟 / 跨越市场状态分界(开盘/午休/收盘),**必须重拉**
3. **检查 Yahoo `marketState`** — 确认是 PREPRE/REGULAR/POSTPOST,字段不一致立即重拉

### A 股市场状态时点(BJT)
| 时点 | 状态 | 数据含义 |
|------|------|---------|
| <09:30 | PREPRE | 昨日收盘价(stale)|
| 09:30-11:30 | REGULAR | 上午盘中实时 |
| 11:30-13:00 | 午休 | 11:30 数据,午后开盘前过期 |
| 13:00-15:00 | REGULAR | 下午盘中实时 |
| 15:00-15:15 | POSTPOST 切换中 | **可能仍是盘中价**,等 15:15 后稳 |
| >15:15 | POSTPOST | 当日收盘价 |

### 反模式(严禁)
- ❌ 用 12:39 午盘数据回答 15:40 用户提问("更新报告"= 必须重拉)
- ❌ "之前已经拉过了" — 跨越市场状态必须重拉,不能图省事
- ❌ 不跑 `Bash date` 直接凭印象写"BJT 12:39"

### 正确做法
- ✅ 用户问"现在如何" → 先 `Bash date` → 看 marketState → 决定是否重拉
- ✅ 收盘后(>15:15)写报告必拉收盘价,不复用盘中数据
- ✅ 数据有"时间戳印章"思维:每个数字都标"X 时 X 分实测"

### 与 NO GUESSING 的关系
- NO GUESSING:**不能编数字**
- 数据新鲜度门:**编对的旧数字也不行**
- 两者叠加 = 数字必须既真实又新鲜

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
- **🎭 Stale 检测**:Yahoo `regularMarketTime` 转 BJT 落后当前 >15min / 跨午休/收盘分界 / >15:15 仍 REGULAR → **立即调 [tool-fallback skill](../tool-fallback/SKILL.md) Playwright 东财实测**,严禁用 stale 数据
- **🔴 Playwright 用完必 `browser_close`**(详见 tool-fallback)

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

### P3.0 [Skill ⭐] Price trigger watch(P3.1 之前必跑)
调 `price-trigger-watch` skill:
- 扫描 positions.md 关注清单全部"触发条件"
- 输出三类清单:**命中**(进 P3.2 走 signal-generation)、**失效**(直接删 watchlist)、**未触发**(报告附录)
- **未触发标的不进 P3.1 / P3.3 深度研究** — 节省 token,避免空跑

### P3.1 [Skill] Bottleneck supply chain scan
调 `bottleneck-analysis` skill,**仅对持仓 + P3.0 命中触发器**做(不再对全 watchlist):
- 瓶颈轮动:GPU → 存储/HBM → 电力/变压器 → 液冷 → PCB → 封装
- 52-week 涨幅找滞涨段
- 海外龙头爆发 → 扫 A 股映射

### P3.2 [Skill ⭐] Signal generation(Router → 5 Gate or 3 Gate)
**所有信号必走** `signal-generation` skill,**Router 自动路由**:
- **新建仓**(标的不在 positions.md):Gate 1+2+2.5+3+4 完整 5 Gate
- **加减仓 / 止盈止损**(已在 positions.md):Router 转 [`signal-rebalance`](../signal-rebalance/SKILL.md) 走 3 Gate(Gate 1+2.5+4,跳 Kelly 和瓶颈)

包含:
- P3.0 命中触发器的新建仓
- 此前所有 open signal 的跟进(状态/价格更新)
- 持仓的卖出/减仓决策

### P3.3 [Skill] Fundamental deepdive(候选标的)
对**新进入候选**(P3.0 命中 + Gate 2.5 通过)调 `fundamental-deepdive` skill 完成 6 维度+G 框架。**P3.0 未触发的标的不在此 phase 处理**。

### P3.4 [Skill] Data validation(背景)
调 `data-validation` skill,启 `run_in_background: true` 验证 subagent。在 P3.7 audit 前必须 review 结果。

### P3.5 [Skill] Discover new stocks
调 `discover-new-stocks` skill:
- 任何信号股价 >¥40 或 52w >200% → 强制找替代
- 每次至少新增 3-5 个未跟踪标的入 watchlist

### P3.6 [Output] Write report + decisions + knowledge updates

写入:
- `reports/YYYY-MM-DD.md`(中文,模板见下方"📄 Report 模板")
- `decisions/YYYY-MM-DD.md`(含每条信号的 4-Gate 输出,模板见下方"📋 Decision Log 模板")
- `decisions/positions.md`(更新当前价/浮盈)
- `research/INDEX.md`(课题进展)
- 状态变化才更新 `knowledge/context.md` / `ai-landscape.md` / `watchlist-sectors.md`(触发条件见 CLAUDE.md "Knowledge Update Triggers")
- 流程缺口写入 `knowledge/prompt-evolution.md`

#### 📄 Report 模板(`reports/YYYY-MM-DD.md`)

```markdown
# 每日情报简报 — YYYY-MM-DD

## 与昨日相比的变化
- 隔夜/上次报告以来的主要变动
- 持仓更新(止损/止盈是否触发)
- 此前信号跟进

## 美股市场概览(前一交易日收盘)
| 资产 | 价格 | 涨跌 | 趋势 |

## 中国市场概览(当日收盘)
| 资产 | 价格 | 涨跌 | 趋势 |

## 大宗商品(最新)
| 资产 | 价格 | 涨跌 | 趋势 |

## 美国新闻与经济
## 中国新闻与经济
## 中美关系与贸易
## 全球地缘政治

## AI与科技
- AI 模型/芯片/资本支出
- 中美 AI 竞争
- AI 相关股票(附代码+价格)
- AI 供应链瓶颈追踪(电力/液冷/HBM/PCB/封装)
- 供应链涨跌幅对比 + 滞后板块标注

## 课题进展跟踪
- research/INDEX.md 中活跃课题的当日进展

## 关键风险与关注清单

## 操作建议 — 中国股票持仓信号
**投资风格:中长期持仓,非短线交易。最短 1 个月。**

### 短期(1-3 月)/ 中期(3-6 月)/ 长期(6-12 月+)
| 操作 | 标的 | 入场逻辑 | 目标/止损 | 赔率 | Kelly 仓位 | 信心 | 催化剂/退出 |

### 重要声明
以上信号仅供信息参考和教育用途,不构成投资建议。
```

#### 📋 Decision Log 模板(`decisions/YYYY-MM-DD.md`)

```markdown
# 决策日志 — YYYY-MM-DD

## 今日发出的信号
### 短期(1-3个月)
| # | 操作 | 标的 | 入场价 | 逻辑 | 反方 | 目标/止损 | 赔率 | Kelly | 信心 | 状态 |

### 中期(3-6个月)/ 长期(6-12个月+)
(同上结构)

## 此前信号跟进
| 原始日期 | # | 标的 | 原始操作 | 当前价 | 盈亏 | 更新 | 新状态 |

## 数据警示(fallback 记录)
- [数据点] — [失败工具] → [fallback 来源]

## 明日关注要点

## Audit(briefing-audit 写入)
```

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
