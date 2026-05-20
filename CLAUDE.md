# Daily News Intelligence Hub

## Purpose

收集、组织、分析每日新闻 → 生成**中国股票(A 股、港股)可执行交易信号**。所有数据收集服务一个目标:**今天该买/卖/持/避哪些中国股票板块或指数?**

四大信息支柱:
1. **美国经济与市场** — Fed/CPI/NFP/关税 — 美国宏观直接传导中国
2. **中国焦点** — 中国经济、PBOC、地产、科技监管
3. **全球地缘** — 中美关系、制裁、冲突 — 中国股票最大风险因子
4. **AI 与科技** — AI 突破、芯片供应链、中美 AI 竞争 — 当代核心投资主题

## 🎯 Skill Index

所有可执行流程封装在 `.claude/skills/`。**优先调用 skill,不要重新实现**。

| 触发场景 | 调用 skill |
|---------|-----------|
| "做今日简报" / `/loop` / 生成 reports/YYYY-MM-DD.md | `daily-briefing` |
| **新建仓信号**(标的不在 positions.md)/ 完整 5 道闸 | **`signal-generation`** ⭐ |
| **加仓 / 减仓 / 止盈 / 止损**(标的已在 positions.md)/ 轻量 3 道闸 | **`signal-rebalance`** ⭐ |
| **扫描 watchlist 触发器命中** / daily-briefing P3.0 | **`price-trigger-watch`** ⭐ |
| 单标的研究 / 产业链下钻 / Gate 3 子调用 | `bottleneck-analysis` |
| "深度研究 XX 公司" / 候选进入 watchlist | `fundamental-deepdive` |
| Session 末尾验证数据 / 用户质疑数据 | `data-validation` |
| 板块扫描 / 找便宜替代 / 拓展 watchlist | `discover-new-stocks` |
| 全 A 股系统扫描 / "我感觉 discover 漏了什么"(⚠️ 备用,非默认) | `sector-scanner` |
| 任何 MCP 工具失败 / 限流 / 超时 | `tool-fallback` |
| **daily-briefing 末尾自检** | **`briefing-audit`** ⭐ |

**用 Skill tool 调用**,例:`Skill(skill="daily-briefing")`。

### 🔴 强制调用规则(防"软跳过")
1. **任何写决策日志的信号必先走 signal-generation OR signal-rebalance** — Router 自动路由
   - 新建仓 → signal-generation 5 Gate
   - 已建仓加减仓 → signal-rebalance 3 Gate
   - 缺 Gate = 信号未入库
2. **`daily-briefing` P3.0 必先调 `price-trigger-watch`** — 未触发标的不进 P3.1/P3.3 深度研究
3. **`daily-briefing` 必须以 `briefing-audit` 结束** — FAIL 项必修正
4. **每个 skill 头部声明 Contract** — 子 skill 依赖显式化

## 🛡 硬约束总览(细则在 skill 内)

| 约束 | 一句话 | SSOT |
|---|---|---|
| 🚫 **NO GUESSING** | 价格/持仓/现金/财报必实测或用户确认,严禁猜测推算 | [`daily-briefing` SKILL](.claude/skills/daily-briefing/SKILL.md) "🚫 NO GUESSING" |
| 🕐 **数据新鲜度** | 每次响应前 `Bash date` + Yahoo `marketState` 必检,跨午休/收盘必重拉 | [`daily-briefing` SKILL](.claude/skills/daily-briefing/SKILL.md) "🕐 数据新鲜度" |
| 🎭 **Stale 必 Playwright** | Yahoo `regularMarketTime` 落后 BJT >15min / 跨午休未刷 → 立即东财 Playwright | [`tool-fallback` SKILL](.claude/skills/tool-fallback/SKILL.md);完用必 `browser_close` |
| 💰 **P&L 术语** | 累计浮盈 ≠ 当日净赚 ≠ 已实现,公式不同不能混 | [`daily-briefing` SKILL](.claude/skills/daily-briefing/SKILL.md) "💰 P&L 术语" |
| 🗂 **SSOT** | 价格只在 positions.md,其他文件引用或带日期戳 | [`daily-briefing` SKILL](.claude/skills/daily-briefing/SKILL.md) "🗂 SSOT" + briefing-audit Check 6 |
| 📊 **滞涨标签 4 维校验** | "滞涨/认知差"必报 52w 涨幅+区间分位/近20日/近5日/放量,任一阈值命中 → 取消标签 | [`signal-generation` SKILL](.claude/skills/signal-generation/SKILL.md) Gate 1 |
| 🎯 **Gate 2.5 可交易性** | 100 股最小单位 + ¥3K floor + 10% cap + 手续费稀释,失败转触发器 | [`signal-generation` SKILL](.claude/skills/signal-generation/SKILL.md) Gate 2.5 |
| 🚫 **创业板权限缺失** | 300xxx / 301xxx 不可交易,扫描必排除 | `decisions/positions.md` 关注清单段 |
| ⚡ **成交确认后默认同步** | 用户报告"X 卖/买了 Y 股 @¥Z" → 立即默认更新 positions.md + decisions/YYYY-MM-DD.md + 总览/P&L,**绝不询问"要不要写入"**;数据同步是 routine 维护不是决策 | 用户 2026-05-19 明确要求 |

## News Categories(具体公司/ticker 在 knowledge/)

- **US Focus**: Fed, CPI/PPI/NFP/GDP/PMI, 关税, 出口管制, 大公司财报
- **China Focus**: GDP/PMI/贸易, PBOC, 地产, 科技监管, A 股(`000001.SS`/`^HSI`/`000300.SS`), CNY/USD
  - 中文搜索关键词:中国经济, 贸易战, 关税, 人民币, A股, 央行
- **Global Geopolitics**: Russia/Ukraine, Middle East, EU, 制裁, NATO/G7/G20/BRICS
- **AI & Technology**: 模型/芯片/HBM/数据中心/电力散热/PCB封装/光通信/AI应用 + 中美 AI 竞争
  - 中文搜索:人工智能, AI芯片, 大模型, 算力, 智算中心, 自动驾驶, 具身智能, 液冷, 变压器, 光模块, 先进封装, PCB, HBM
- **Financial Markets**: 美股(`^GSPC`/`^IXIC`/`^DJI`)/A股/港股 / 商品(`GC=F`/`SI=F`/`CL=F`/`BZ=F`/`HG=F`/`NG=F`)/ DXY(`DX-Y.NYB`)/USDCNY(`CNY=X`)/ 美债 2Y/10Y/30Y(`^TNX`)

*完整 ticker 表 / 板块图谱见 `knowledge/ai-landscape.md` 和 `knowledge/watchlist-sectors.md`*

## Available Tools

| Tool | 用途 | Fallback |
|---|---|---|
| **Yahoo Finance** (`mcp__yfinance__*`) | 股价/财报/新闻/期权 | `tool-fallback` → 东财 Playwright |
| **Exa** (`mcp__exa__*`) | 语义搜索/抓取(中英文) | 等 60-120s 重试 → Playwright |
| **FRED** (`mcp__FRED_MCP_Server__*`) | 美国宏观(CPI/GDP/失业/利率) | `fred.stlouisfed.org/series/{ID}` |
| **Alpha Vantage** (`mcp__alphavantage__*`) | 黄金/白银/技术指标/外汇/情感 | tradingview/tradingeconomics |
| **Playwright** (`mcp__playwright__*`) | JS/付费墙/终极 fallback | (本身) — **用完必 `browser_close`** |
| **天天基金网** (Playwright) | 中文基金 NAV — `https://h5.1234567.com.cn/app/fund-details/?fCode={code}` | — |

### Price Data Rules
- **永远 Yahoo Finance `get_stock_info`** 拿股价,不用 Exa 搜
- **A 股**:`.SS`(上交所) / `.SZ`(深交所)
- **基金/QDII**:天天基金网 via Playwright
- **黄金现货(¥)**:Alpha Vantage 或 Exa 搜上海金交所
- **任何 stale / 失败 → 立即 [`tool-fallback`](.claude/skills/tool-fallback/SKILL.md)**

## File Structure

```
daily-news/
├── CLAUDE.md                    # 项目说明 + skill 索引(本文件)
├── .claude/skills/              # 🎯 11 个 skill(流程 SSOT)
│   ├── daily-briefing/          # 主流程编排(17 步 + audit)
│   ├── price-trigger-watch/     # ⭐ P3.0 触发器扫描(命中才下钻)
│   ├── signal-generation/       # ⭐ 新建仓 5 道闸(Gate 1+2+2.5+3+4)
│   ├── signal-rebalance/        # ⭐ 加减仓 3 道闸(Gate 1+2.5+4)
│   ├── bottleneck-analysis/     # 瓶颈资产框架
│   ├── fundamental-deepdive/    # 6 维度基本面
│   ├── data-validation/         # 数据验证
│   ├── discover-new-stocks/     # 新标的发掘
│   ├── sector-scanner/          # ⭐ 全 A 股系统扫描(L1+L2 Python+L3 Skill)
│   ├── tool-fallback/           # 工具失败 SOP
│   └── briefing-audit/          # ⭐ 末尾自检
├── knowledge/                   # 数据 SSOT(非流程)
│   ├── context.md               # 全球宏观/地缘/市场状态
│   ├── ai-landscape.md          # AI 产业图谱 + ticker
│   ├── watchlist-sectors.md     # 板块/子链/标的
│   ├── bottleneck-framework.md  # 瓶颈框架数据参考
│   ├── tool-fallbacks.md        # Fallback URL + Playwright 模板
│   └── prompt-evolution.md      # System prompt 改进日志
├── reports/                     # 每日简报(中文)— YYYY-MM-DD.md
├── decisions/                   # 决策记忆
│   ├── positions.md             # 当前持仓 & 关注清单(SSOT)
│   ├── YYYY-MM-DD.md            # 每日决策日志
│   └── review.md                # 周期回顾
├── research/INDEX.md            # 课题总索引
├── tools/                       # Python 工具
│   ├── technical.py             # MA/RSI/MACD/BB/ATR
│   ├── kelly.py                 # Kelly 仓位
│   ├── save_prices.py           # 价格新鲜度
│   └── scanner/                 # ⭐ 全 A 股扫描器(sector-scanner skill)
│       ├── fetch_eastmoney.py   # L1 抓取(AkShare)
│       ├── score.py             # L2 4 维评分
│       ├── ai_keywords.py       # 4 链关键词词典
│       └── output/              # CSV 产物
├── data/prices/                 # 历史价格 JSON
├── data/scanner/                # ⭐ 全 A 股快照 raw JSON
└── sources.md                   # 跟踪源
```

## Knowledge Base 分工

**核心规则**:knowledge/ = 数据,skills/ = 流程,CLAUDE.md = 索引。

- `knowledge/context.md` — 宏观/地缘/市场状态(每报告后增量更新)
- `knowledge/ai-landscape.md` — AI 产业图谱(重大 AI 进展时更新)
- `knowledge/watchlist-sectors.md` — 板块/标的(新标的发现时更新)
- `knowledge/bottleneck-framework.md` — **数据参考**(图谱/对标/持仓诊断)— 流程在 `bottleneck-analysis` skill
- `knowledge/tool-fallbacks.md` — **URL 速查 + Playwright 模板** — 流程在 `tool-fallback` skill
- `knowledge/prompt-evolution.md` — System prompt 改进日志

### Knowledge Update Triggers
- `context.md`:央行变利率/转向、新制裁/关税、地缘升级、宏观数据 surprise、市场 regime shift
- `ai-landscape.md`:重大模型/benchmark、新出口管制/实体清单、估值因 AI 新闻 >10% 变动、AI 监管、供应链中断、新瓶颈出现、定价权变化
- `watchlist-sectors.md`:新板块/子板块、现有板块新公司、产业链下钻发现、产业集群、板块逻辑被证伪/确认

## Memory & Decision 文件结构

详细模板在 [`daily-briefing` SKILL.md](.claude/skills/daily-briefing/SKILL.md);此处仅列文件:
- `decisions/YYYY-MM-DD.md` — 当日信号 + 4 道闸输出 + 跟进 + fallback 记录 + 明日关注
- `decisions/positions.md` — Living:持仓 / 关注清单 / 平仓(SSOT)
- `decisions/review.md` — 周期回顾(准确率/教训/偏差)

## Report Format

详细模板在 [`daily-briefing` SKILL.md](.claude/skills/daily-briefing/SKILL.md) Phase 3。简报必含:与昨变化 / 美股+中国市场+商品概览 / 美中地缘 AI 新闻 / 课题进展 / 风险 / **操作建议**(短/中/长期 + signal-generation 4 道闸输出)/ 重要声明。

## Guidelines

- Cite sources with URLs
- Distinguish facts from analysis
- Note data timestamps — markets move fast
- Flag low-confidence/unverified info
- Keep reports concise — focus on what matters for trading decisions
