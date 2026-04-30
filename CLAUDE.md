# Daily News Intelligence Hub

## Purpose

This project collects, organizes, and analyzes daily news to generate **actionable trading signals for China stocks (A-shares, Hong Kong)**. All news and data collection serves one end goal: **should I buy, sell, hold, or avoid specific China stock sectors/indices today?**

Three information pillars feed the analysis:

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

1. **Search** — Use Exa to find today's top stories; search in **both English and Chinese** for China and AI coverage
2. **Fetch** — Use Exa fetch or Playwright for paywalled/JS-heavy sites
3. **Extract prices** — Use Yahoo Finance MCP for US indices, China indices, commodities, forex (USD/CNY), and AI stocks
4. **Summarize** — Write a structured daily briefing in `reports/YYYY-MM-DD.md` (English) and `reports/YYYY-MM-DD-cn.md` (Chinese)
5. **Flag** — Highlight market-moving events, US-China risks, AI developments, and trading implications
6. **Track decisions** — Log trading signals to `decisions/YYYY-MM-DD.md` and update `decisions/positions.md`
7. **Update knowledge** — Update `knowledge/context.md` and `knowledge/ai-landscape.md` with any state changes
8. **Reference history** — At session start, read knowledge base and recent decision logs for continuity

## Report Format

Each daily report should follow this structure:

```markdown
# Daily Intelligence Briefing — YYYY-MM-DD

## US Market Snapshot
| Asset | Price | Change | Trend |
|-------|-------|--------|-------|
| S&P 500 | ... | ... | ... |
| NASDAQ | ... | ... | ... |
| DXY | ... | ... | ... |
| US 10Y Yield | ... | ... | ... |

## China Market Snapshot
| Asset | Price | Change | Trend |
|-------|-------|--------|-------|
| Shanghai Composite | ... | ... | ... |
| Hang Seng | ... | ... | ... |
| USD/CNY | ... | ... | ... |

## Commodities
| Asset | Price | Change | Trend |
|-------|-------|--------|-------|
| Gold | ... | ... | ... |
| Silver | ... | ... | ... |
| Oil (WTI) | ... | ... | ... |
| Copper | ... | ... | ... |

## US News & Economy
- ...

## China News & Economy
- ...

## US-China Relations & Trade
- ...

## Global Geopolitics
- ...

## AI & Technology
- ...

## Key Risks & Watchlist
- ...

## Action Items — China Stock Trading Signals
For each signal, state: **Action** (Buy / Sell / Hold / Avoid), **Target** (sector, index, or specific stock), **Reasoning**, **Confidence** (High / Medium / Low), and **Time Horizon** (intraday / short-term / medium-term).

| Action | Target | Reasoning | Confidence | Horizon |
|--------|--------|-----------|------------|---------|
| Buy/Sell/Hold/Avoid | sector or ticker | why | H/M/L | timeframe |

### Key China Sectors to Monitor
- Tech / AI (Alibaba, Tencent, Baidu, SenseTime, iFlytek)
- AI Chips & Hardware (Cambricon, SMIC, Hua Hong, Zhongji Innolight)
- EV / New Energy (BYD, NIO, Li Auto, CATL)
- Financials / Banks (ICBC, China Merchants Bank)
- Property (Vanke, Country Garden, Longfor)
- Consumer / Retail (Moutai, Li Ning, Anta)
- Semiconductors (SMIC, Hua Hong, NAURA)
- Defense / Military
- Healthcare / Biotech

### Signal Framework
Signals are derived by combining:
1. **Macro signals**: US Fed policy direction, USD/CNY movement, US-China trade status
2. **China domestic signals**: PBOC actions, stimulus, PMI, property data, regulatory tone
3. **Sentiment signals**: news sentiment, capital flows (northbound/southbound via Stock Connect)
4. **Technical signals**: index trend, support/resistance levels, volume patterns
5. **Geopolitical risk**: escalation vs de-escalation in US-China, Taiwan, sanctions

### Important Disclaimer
These signals are for informational and educational purposes only. They are NOT financial advice. Always do your own research and consider your risk tolerance before trading.
```

## File Structure

```
daily-news/
├── CLAUDE.md                    # System prompt and project config
├── knowledge/                   # Living knowledge base (accumulated context)
│   ├── context.md               # Global macro/geopolitical/market state
│   └── ai-landscape.md          # AI industry map, key players, supply chain
├── reports/                     # Daily briefing reports
│   ├── YYYY-MM-DD.md            # English version
│   └── YYYY-MM-DD-cn.md         # Chinese version (中文版)
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
# Decision Log — YYYY-MM-DD

## Signals Issued Today
| # | Action | Target | Entry Price | Reasoning | Confidence | Horizon | Status |
|---|--------|--------|-------------|-----------|------------|---------|--------|
| 1 | Buy | ... | ... | ... | H/M/L | ... | OPEN |

## Follow-up on Prior Signals
| Original Date | # | Target | Original Action | Current Price | P&L | Update | New Status |
|---------------|---|--------|-----------------|---------------|-----|--------|------------|
| 2026-04-29 | 1 | ... | Buy | ... | +2% | ... | OPEN/CLOSED/STOPPED |

## Key Context for Tomorrow
- Upcoming events that may affect open positions
- Data releases to watch
- Risks carried forward
```

### 2. Positions Tracker (`decisions/positions.md`)
A **living document** updated daily — the single source of truth for what's active:

```markdown
# Active Positions & Watchlist

## Open Positions
| Opened | Target | Action | Entry Price | Current Price | P&L | Stop Loss | Take Profit | Status | Notes |
|--------|--------|--------|-------------|---------------|-----|-----------|-------------|--------|-------|

## Watchlist (Waiting for Entry)
| Added | Target | Planned Action | Trigger Condition | Notes |
|-------|--------|----------------|-------------------|-------|

## Recently Closed
| Opened | Closed | Target | Action | Entry | Exit | P&L | Reason |
|--------|--------|--------|--------|-------|------|-----|--------|
```

### 3. Periodic Review (`decisions/review.md`)
Updated weekly or on-demand. Tracks signal accuracy and lessons:

```markdown
# Signal Review

## Accuracy Tracker
| Period | Total Signals | Correct | Wrong | Accuracy | Notes |
|--------|---------------|---------|-------|----------|-------|

## Lessons Learned
- What worked, what didn't, pattern adjustments

## Bias Check
- Am I consistently wrong on a sector? Over-confident? Under-reacting to geopolitical risk?
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
