# Daily News Intelligence Hub

## Purpose

This project collects, organizes, and analyzes daily news to generate **actionable trading signals for China stocks (A-shares, Hong Kong)**. All news and data collection serves one end goal: **should I buy, sell, hold, or avoid specific China stock sectors/indices today?**

Four information pillars feed the analysis:

1. **US Economy & Markets** — Fed policy, inflation, jobs, earnings, trade policy — because US macro directly impacts China markets
2. **China Focus** — China's economy, trade data, PBOC policy, stimulus, regulatory changes, property market, tech sector
3. **Global Geopolitics** — US-China tensions, tariffs, sanctions, conflicts — the biggest risk factor for China stocks
4. **AI & Technology** — AI breakthroughs, chip supply chain, US-China AI rivalry, AI regulation — the defining investment theme of this era

## News Categories

### US Focus
- Federal Reserve decisions, rate expectations, Fed speeches
- US economic data (CPI, PPI, NFP, GDP, PMI, consumer sentiment, housing)
- US fiscal policy, budget, debt ceiling
- US trade policy — tariffs, export controls, trade agreements
- US domestic politics affecting markets
- Major US corporate earnings and sector trends

### China Focus
- **China Economy**: GDP, PMI, trade balance, industrial production, retail sales, property market
- **China Policy**: PBOC (People's Bank of China) decisions, stimulus measures, regulatory changes
- **US-China Relations**: tariffs, sanctions, tech restrictions, diplomatic developments, Taiwan
- **China Markets**: Shanghai Composite (000001.SS), Hang Seng (^HSI), CSI 300, A-shares
- **China Trade**: export/import data, Belt & Road, trade partners, supply chain shifts
- **China Domestic**: tech sector regulation, property crisis, local government debt, demographics
- **CNY/USD**: yuan exchange rate movements and PBOC intervention signals
- **Search Sources**: Exa search in both English and Chinese (搜索中英文新闻) — use Chinese keywords like 中国经济, 贸易战, 关税, 人民币, A股, 央行 for domestic China coverage

### Global Geopolitics
- Russia/Ukraine, Middle East, EU politics
- Trade wars, sanctions, tariffs (beyond US-China)
- Elections and government transitions worldwide
- Military/defense developments
- International organizations (UN, NATO, G7/G20, BRICS, SCO)

### AI & Technology Focus
- **AI Models & Breakthroughs**: OpenAI, Anthropic, Google DeepMind, Meta AI, Chinese labs (DeepSeek, Baidu ERNIE, Alibaba Qwen, ByteDance, Zhipu AI, Moonshot AI)
- **AI Infrastructure / Chips**: NVIDIA (NVDA), AMD, TSMC (TSM), Intel, Broadcom; China: SMIC, Cambricon (688256.SS), Hua Hong (1347.HK)
- **AI Cloud & Data Centers**: MSFT Azure, GOOG Cloud, AMZN AWS, Alibaba Cloud, Baidu Cloud, Tencent Cloud; SMCI, Dell
- **AI Applications**: enterprise SaaS, autonomous driving (Baidu Apollo, Tesla FSD, Waymo), robotics, AI agents, AI coding
- **US-China AI Rivalry**: chip export controls, entity list updates, open-source vs closed models, AI talent flow
- **AI Regulation**: US executive orders, EU AI Act, China AI governance rules
- **AI Investment Themes**: capex cycle (hyperscaler spending), AI picks-and-shovels (chips, networking, cooling), AI software monetization
- **Search Keywords (Chinese)**: 人工智能, AI芯片, 大模型, DeepSeek, 算力, 智算中心, 自动驾驶, 具身智能

### Financial Markets & Trading
- **US Equities**: S&P 500 (^GSPC), NASDAQ (^IXIC), Dow Jones (^DJI), sector rotation
- **China Equities**: Shanghai Composite (000001.SS), Hang Seng (^HSI), CSI 300 (000300.SS)
- **Commodities**: Gold (GC=F), Silver (SI=F), Oil WTI (CL=F), Oil Brent (BZ=F), Copper (HG=F), Natural Gas (NG=F)
- **Currencies / Forex**: DXY (DX-Y.NYB), EUR/USD, USD/CNY, USD/JPY
- **Bonds / Rates**: US Treasury yields (2Y, 10Y, 30Y), Fed funds rate, China government bond yields
- **Crypto**: Bitcoin, Ethereum (if market-relevant)
- **Economic Calendar**: track upcoming data releases for both US and China

## Available Tools

### Currently Connected
- **Exa** (`mcp__exa__web_search_exa`, `mcp__exa__web_fetch_exa`) — semantic web search and content extraction; supports Chinese-language queries for China domestic news
- **Yahoo Finance** (`mcp__yfinance__*`) — stock prices, financials, news, options for US/China/global tickers
- **FRED** (`mcp__FRED_MCP_Server__*`) — US economic indicators (CPI, GDP, unemployment, NFP, rates, retail sales, inflation)
- **Alpha Vantage** (`mcp__alphavantage__*`) — gold/silver spot prices, technical indicators (RSI, MACD, BBANDS), forex rates, news sentiment, earnings calendar, commodity prices
- **Playwright** (`mcp__playwright__*`) — browser automation for JS-heavy or paywalled sites

### Key Yahoo Finance Tickers
| Asset | Ticker | Notes |
|-------|--------|-------|
| S&P 500 | `^GSPC` | US large cap index |
| NASDAQ | `^IXIC` | US tech-heavy index |
| Dow Jones | `^DJI` | US blue chip index |
| Shanghai Composite | `000001.SS` | China A-shares |
| Hang Seng | `^HSI` | Hong Kong index |
| Gold | `GC=F` | Futures |
| Silver | `SI=F` | Futures |
| Oil WTI | `CL=F` | Futures |
| Oil Brent | `BZ=F` | Futures |
| DXY (USD index) | `DX-Y.NYB` | Dollar strength |
| USD/CNY | `CNY=X` | Yuan exchange rate |
| US 10Y Treasury | `^TNX` | Yield |
| Copper | `HG=F` | Futures |

### Key AI & Tech Tickers
| Company | US Ticker | HK/China Ticker | AI Role |
|---------|-----------|-----------------|---------|
| NVIDIA | `NVDA` | — | GPU / AI training chips |
| AMD | `AMD` | — | GPU / AI accelerators |
| TSMC | `TSM` | `2330.TW` | Chip fabrication |
| Broadcom | `AVGO` | — | AI networking chips |
| Super Micro | `SMCI` | — | AI server hardware |
| Microsoft | `MSFT` | — | Azure AI / OpenAI partner |
| Alphabet | `GOOGL` | — | DeepMind / Cloud AI |
| Meta | `META` | — | Llama models / AI infra |
| Amazon | `AMZN` | — | AWS AI / custom chips |
| Baidu | `BIDU` | `9888.HK` | ERNIE / Apollo Go |
| Alibaba | `BABA` | `9988.HK` | Qwen models / Cloud AI |
| Tencent | — | `0700.HK` | AI integration / Cloud |
| SenseTime | — | `0020.HK` | AI vision / models |
| Cambricon | — | `688256.SS` | AI chips (A-share) |
| SMIC | — | `0981.HK` / `688981.SS` | Chip fabrication (China) |
| Zhongji Innolight | — | `300308.SZ` | AI optical modules |

### Recommended Additional Data Sources

| Channel | What It Provides |
|---------|-----------------|
| **NewsAPI** | Aggregated headlines from 80K+ sources — newsapi.org |
| **Finnhub** | Real-time quotes, earnings calendar — finnhub.io |

## Daily Workflow

When asked to collect daily news (`/loop` or manual run):

### Phase 1: Context Loading (do this FIRST)
1. **Load knowledge base** — Read `knowledge/context.md` and `knowledge/ai-landscape.md` to understand current world state
2. **Load open positions** — Read `decisions/positions.md` and the last 2-3 daily decision logs to understand active trades and recent signals
3. **Identify follow-ups** — Note which open positions need price updates, stop-loss/take-profit checks, and which watchlist items may have triggered

### Phase 2: Data Collection
4. **Extract prices** — Use Yahoo Finance for indices, commodities, forex. Use Alpha Vantage for technical indicators (RSI, MACD, BBANDS) on key positions, commodity spot prices, and news sentiment scores
5. **Check positions** — Compare current prices against open position stop-loss and take-profit levels. Flag any triggers
6. **Search news** — Use Exa with the minimum query set below; search in **both English and Chinese**
7. **Fetch details** — Use Exa fetch or Playwright for paywalled/JS-heavy articles that seem high-impact
8. **Pull macro data** — Use FRED for any new US economic releases (CPI, NFP, GDP, etc.)

### Phase 3: Analysis & Output
9. **Write report** — Structured daily briefing in `reports/YYYY-MM-DD.md` (Chinese 中文). Include a "与昨日相比的变化" summary and a dedicated "AI与科技" section. All report content in Chinese; keep ticker symbols, financial terms (P/E, SAAR, WTI etc.) in English
10. **Generate signals** — New trading signals with reasoning, plus follow-up on all prior open signals
11. **Track decisions** — Log to `decisions/YYYY-MM-DD.md` and update `decisions/positions.md`
12. **Update knowledge** — Update knowledge docs ONLY when state actually changes (see Knowledge Update Triggers below)

### Minimum Exa Search Queries
Run at least these searches each session (add more as needed):

| # | Query (English) | Query (Chinese) | Covers |
|---|----------------|-----------------|--------|
| 1 | `US economy Federal Reserve today` | — | Fed, US macro |
| 2 | `China economy trade PBOC today` | `中国经济 央行 贸易 今日` | China macro |
| 3 | `US China relations sanctions tariffs` | `中美关系 制裁 关税` | Geopolitics |
| 4 | `AI artificial intelligence chips breakthrough` | `人工智能 大模型 AI芯片 算力` | AI sector |
| 5 | `China stock market A-shares Hong Kong` | `A股 港股 行情` | China markets |
| 6 | `oil gold commodities prices today` | — | Commodities |

### Data Freshness Rules
- **US market data**: prior trading day's close (US markets close after Asia opens)
- **China market data**: same-day close (Shanghai/HK close before US opens)
- **Commodities/Forex**: latest available (near real-time via futures)
- Always label which session/date each price comes from in the report tables

### Tool Usage Guide
| Tool | Primary Use | When to Prefer |
|------|------------|----------------|
| Yahoo Finance | Stock prices, company info, earnings, news | Default for all price data |
| FRED | US macro indicators (CPI, GDP, unemployment, rates) | When new US economic data releases |
| Alpha Vantage | Technical indicators (RSI, MACD, BBANDS), commodity spot, forex, sentiment | When analyzing specific stock technicals or need sentiment scores |
| Exa | News search + content extraction | All news gathering |
| Playwright | Browser automation | Paywalled sites, JS-heavy pages that Exa can't extract |

### Knowledge Update Triggers
Update `knowledge/context.md` when:
- Central bank changes rates or shifts stance (Fed, PBOC, ECB, BOJ)
- New sanctions, tariffs, or trade policy enacted
- Geopolitical status changes (ceasefire, escalation, new conflict)
- Major economic data surprises (GDP miss/beat, employment shift)
- Market regime shifts (breakout, crash, new range established)

Update `knowledge/ai-landscape.md` when:
- Major model release or breakthrough benchmark
- New chip export controls or entity list changes
- Company valuation shifts >10% on AI news
- New AI regulation enacted
- Supply chain disruption (fab issues, chip shortages)

## Report Format

Each daily report should follow this structure:

```markdown
# 每日情报简报 — YYYY-MM-DD

## 与昨日相比的变化
- 隔夜/上次报告以来的主要变动
- 持仓更新（止损/止盈是否触发）
- 此前信号跟进（昨日建议的后续）

## 美股市场概览（前一交易日收盘）
| 资产 | 价格 | 涨跌 | 趋势 |
|------|------|------|------|
| 标普500 | ... | ... | ... |
| 纳斯达克 | ... | ... | ... |
| 美元指数 (DXY) | ... | ... | ... |
| 美国10年期国债 | ... | ... | ... |

## 中国市场概览（当日收盘）
| 资产 | 价格 | 涨跌 | 趋势 |
|------|------|------|------|
| 上证综指 | ... | ... | ... |
| 恒生指数 | ... | ... | ... |
| 美元/人民币 | ... | ... | ... |

## 大宗商品（最新）
| 资产 | 价格 | 涨跌 | 趋势 |
|------|------|------|------|
| 黄金 | ... | ... | ... |
| 白银 | ... | ... | ... |
| 原油 (WTI) | ... | ... | ... |
| 铜 | ... | ... | ... |

## 美国新闻与经济
- ...

## 中国新闻与经济
- ...

## 中美关系与贸易
- ...

## 全球地缘政治
- ...

## AI与科技
- AI模型发布、芯片新闻、AI资本支出/财报
- 中美AI竞争动态
- AI相关股票（附代码和价格变动）

## 关键风险与关注清单
- ...

## 操作建议 — 中国股票交易信号
每个信号注明：**操作**（买入/卖出/持有/回避）、**标的**（板块、指数或个股）、**逻辑**、**信心**（高/中/低）、**时间周期**

| 操作 | 标的 | 逻辑 | 信心 | 周期 |
|------|------|------|------|------|
| 买入/卖出/持有/回避 | 板块或代码 | 原因 | 高/中/低 | 时间 |

### 重点关注的中国板块
- 科技/AI（阿里巴巴、腾讯、百度、商汤、科大讯飞）
- AI芯片与硬件（寒武纪、中芯国际、华虹、中际旭创）
- 新能源车（比亚迪、蔚来、理想、宁德时代）
- 金融/银行（工商银行、招商银行）
- 房地产（万科、碧桂园、龙湖）
- 消费/零售（茅台、李宁、安踏）
- 半导体（中芯国际、华虹、北方华创）
- 国防军工
- 医疗/生物科技

### 信号框架
信号由以下维度综合得出：
1. **宏观信号**：美联储政策方向、美元/人民币走势、中美贸易状态
2. **中国国内信号**：央行动作、刺激政策、PMI、房地产数据、监管基调
3. **情绪信号**：新闻情绪、资金流向（陆股通/港股通）
4. **技术信号**：指数趋势、支撑/阻力位、成交量
5. **地缘政治风险**：中美关系升级/缓和、台海、制裁

### 重要声明
以上信号仅供信息参考和教育用途，不构成投资建议。投资前请自行研究并评估风险承受能力。
```

## File Structure

```
daily-news/
├── CLAUDE.md                    # System prompt and project config
├── knowledge/                   # Living knowledge base (accumulated context)
│   ├── context.md               # Global macro/geopolitical/market state
│   └── ai-landscape.md          # AI industry map, key players, supply chain
├── reports/                     # Daily briefing reports (中文)
│   └── YYYY-MM-DD.md            # Chinese version (中文版)
├── decisions/                   # Trading decision memory system
│   ├── positions.md             # Current open positions & watchlist (living document)
│   ├── YYYY-MM-DD.md            # Daily decision log
│   └── review.md               # Weekly/periodic review of signal accuracy
├── data/                        # Raw data snapshots (optional)
└── sources.md                   # Tracked sources and RSS feeds
```

## Knowledge Base System

The knowledge base (`knowledge/`) is a set of **living documents** that accumulate understanding across sessions. Unlike daily reports (snapshots of one day), knowledge docs represent **the current state of the world** and are updated incrementally.

### `knowledge/context.md` — Global Context
Sections: Geopolitical State, US Economic State, China Economic State, US-China Relations, Market Regime. Updated after each daily report with any state changes.

### `knowledge/ai-landscape.md` — AI Industry Map
Sections: US AI Leaders, China AI Leaders, Chip Supply Chain, AI Regulation, US-China AI Rivalry, Investment Themes. Updated when major AI developments occur.

### How to Use Knowledge Base
1. **Start of session**: Read `knowledge/context.md` and `knowledge/ai-landscape.md` instead of re-reading all past daily reports
2. **After daily report**: Update knowledge docs with any state changes (e.g., if PBOC cuts rates, update China Economic State)
3. **Key principle**: Knowledge docs answer "what is the current state?" while daily reports answer "what happened today?"

## Memory & Decision Tracking System

### 1. Daily Decision Log (`decisions/YYYY-MM-DD.md`)
Created alongside each daily report. Records:

```markdown
# 决策日志 — YYYY-MM-DD

## 今日发出的信号
| # | 操作 | 标的 | 入场价格 | 逻辑 | 信心 | 周期 | 状态 |
|---|------|------|----------|------|------|------|------|
| 1 | 买入 | ... | ... | ... | 高/中/低 | ... | 开仓 |

## 此前信号跟进
| 原始日期 | # | 标的 | 原始操作 | 当前价格 | 盈亏 | 更新 | 新状态 |
|----------|---|------|----------|----------|------|------|--------|
| 2026-04-29 | 1 | ... | 买入 | ... | +2% | ... | 开仓/平仓/止损 |

## 明日关注要点
- 可能影响持仓的即将事件
- 需关注的数据发布
- 延续的风险
```

### 2. Positions Tracker (`decisions/positions.md`)
A **living document** updated daily — the single source of truth for what's active:

```markdown
# 活跃持仓与关注清单

## 开仓持仓
| 开仓日期 | 标的 | 操作 | 入场价 | 当前价 | 盈亏 | 止损 | 止盈 | 状态 | 备注 |
|----------|------|------|--------|--------|------|------|------|------|------|

## 关注清单（等待入场）
| 添加日期 | 标的 | 计划操作 | 触发条件 | 备注 |
|----------|------|----------|----------|------|

## 近期平仓
| 开仓 | 平仓 | 标的 | 操作 | 入场 | 出场 | 盈亏 | 原因 |
|------|------|------|------|------|------|------|------|
```

### 3. Periodic Review (`decisions/review.md`)
Updated weekly or on-demand. Tracks signal accuracy and lessons:

```markdown
# 信号回顾

## 准确率追踪
| 时期 | 总信号数 | 正确 | 错误 | 准确率 | 备注 |
|------|----------|------|------|--------|------|

## 经验教训
- 哪些有效、哪些无效、模式调整

## 偏差检查
- 是否在某个板块持续判断错误？过度自信？对地缘政治风险反应不足？
```

### How Memory Works Across Sessions
1. **Before generating new signals**: Always read `decisions/positions.md` and the last 2-3 daily decision logs to understand open positions and recent context
2. **After generating signals**: Update `decisions/YYYY-MM-DD.md` with new signals and follow-ups, then update `decisions/positions.md`
3. **Price updates**: When fetching new prices, check against open positions for stop-loss/take-profit triggers
4. **Continuity**: Each day's report should reference what changed since yesterday — don't repeat the same signal without acknowledging prior context

## Guidelines

- Cite sources with URLs
- Distinguish facts from analysis/opinion
- Note data timestamps — markets move fast
- Flag low-confidence or unverified information
- Keep reports concise — highlight what matters for trading decisions and geopolitical awareness
