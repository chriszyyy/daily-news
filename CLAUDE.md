# Daily News Intelligence Hub

## Purpose

This project collects, organizes, and analyzes daily news to support:

1. **Global Political Situation Analysis** — geopolitical events, international relations, conflicts, elections, policy changes, sanctions, trade agreements
2. **Financial Market Intelligence** — market-moving news, economic indicators, central bank decisions, earnings, sector trends

## News Categories

### Geopolitics & Politics
- US domestic politics and policy
- US-China relations, EU politics, Russia/Ukraine, Middle East
- Trade wars, sanctions, tariffs
- Elections and government transitions
- Military/defense developments
- International organizations (UN, NATO, G7/G20, BRICS)

### Financial Markets & Trading
- **Equities**: S&P 500, NASDAQ, Dow Jones, major individual stocks, sector rotation
- **Commodities**: Gold, Silver, Oil (WTI & Brent), Natural Gas, Copper, Wheat
- **Currencies / Forex**: USD index (DXY), EUR/USD, USD/CNY, major pairs
- **Bonds / Rates**: US Treasury yields (2Y, 10Y, 30Y), Fed funds rate, central bank decisions
- **Crypto**: Bitcoin, Ethereum (if market-relevant)
- **Economic Indicators**: CPI, PPI, NFP/jobs, GDP, PMI, consumer sentiment

## Available Tools

### Currently Connected
- **Exa** (`mcp__exa__web_search_exa`, `mcp__exa__web_fetch_exa`) — semantic web search and content extraction
- **Playwright** (`mcp__playwright__*`) — browser automation for sites that require interaction or JavaScript rendering

### Recommended Additional MCP Servers / Data Channels

To get reliable, real-time financial data, consider adding these MCP servers or data sources:

| Channel | What It Provides | How to Find |
|---------|-----------------|-------------|
| **Yahoo Finance API / yfinance** | Stock prices, commodities, forex, indices — free, reliable | Python library or MCP wrapper |
| **Alpha Vantage** | Stock, forex, crypto, commodities with API key (free tier available) | alphavantage.co |
| **FRED (Federal Reserve Economic Data)** | US economic indicators (CPI, GDP, unemployment, rates) | fred.stlouisfed.org — has API |
| **Finnhub** | Real-time stock quotes, news, earnings calendar | finnhub.io — free tier |
| **Polygon.io** | Stocks, options, forex, crypto tick data | polygon.io |
| **NewsAPI** | Aggregated news headlines from 80K+ sources | newsapi.org |
| **RSS feeds** | Reuters, Bloomberg, AP, FT, WSJ — structured headline feeds | Direct HTTP fetch |
| **X/Twitter** | Breaking news, sentiment from financial accounts | API or scraping |

## Daily Workflow

When asked to collect daily news (`/loop` or manual run):

1. **Search** — Use Exa to find today's top stories across geopolitics and finance
2. **Fetch** — Use Exa fetch or Playwright for paywalled/JS-heavy sites
3. **Extract prices** — Pull current prices for key assets (indices, gold, silver, oil, DXY)
4. **Summarize** — Write a structured daily briefing in `reports/YYYY-MM-DD.md`
5. **Flag** — Highlight market-moving events and geopolitical risks

## Report Format

Each daily report should follow this structure:

```markdown
# Daily Intelligence Briefing — YYYY-MM-DD

## Market Snapshot
| Asset | Price | Change | Trend |
|-------|-------|--------|-------|
| S&P 500 | ... | ... | ... |
| Gold | ... | ... | ... |
| Silver | ... | ... | ... |
| Oil (WTI) | ... | ... | ... |
| DXY | ... | ... | ... |

## Top Geopolitical Developments
- ...

## Financial / Market News
- ...

## Key Risks & Watchlist
- ...

## Trading Implications
- ...
```

## File Structure

```
daily-news/
├── CLAUDE.md              # This file
├── reports/               # Daily briefing reports
│   └── YYYY-MM-DD.md
├── data/                  # Raw data snapshots (optional)
└── sources.md             # Tracked sources and RSS feeds
```

## Guidelines

- Cite sources with URLs
- Distinguish facts from analysis/opinion
- Note data timestamps — markets move fast
- Flag low-confidence or unverified information
- Keep reports concise — highlight what matters for trading decisions and geopolitical awareness
