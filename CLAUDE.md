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
- **AI模型与突破**: 美国/中国领先实验室的模型发布、基准测试、能力突破
- **AI基础设施/芯片**: GPU、AI加速器、芯片代工、芯片出口管制
- **AI存储/HBM**: 高带宽内存、NAND闪存、企业SSD — 供需缺口与涨价周期
- **AI云与数据中心**: 超大规模厂商资本支出、云AI服务
- **AI电力与散热**: 变压器短缺、液冷渗透率、数据中心能耗 — 当前最大瓶颈
- **AI PCB与先进封装**: 高多层PCB、CCL材料、CoWoS封装 — AI推理芯片带来量价齐升
- **AI网络/光通信**: 光模块（800G/1.6T）、CPO共封装光学、AI交换机
- **AI应用**: 企业SaaS、自动驾驶、机器人、AI智能体
- **中美AI竞争**: 芯片出口管制、实体清单、开源vs闭源模型
- **AI监管**: 美国行政令、欧盟AI法案、中国AI治理规则
- **搜索关键词（中文）**: 人工智能, AI芯片, 大模型, 算力, 智算中心, 自动驾驶, 具身智能, 液冷, 变压器, 光模块, 先进封装, PCB, HBM

*具体公司、ticker、产业链图谱详见 `knowledge/ai-landscape.md` 和 `knowledge/watchlist-sectors.md`*

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
- **天天基金网** (via Playwright) — Chinese fund NAV lookup. URL: `https://h5.1234567.com.cn/app/fund-details/?fCode={基金代码}`. Use for QDII funds and domestic funds not available on Yahoo Finance (e.g., 021277 广发全球精选C)

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

*AI/科技/供应链相关ticker详见 `knowledge/ai-landscape.md`；A股细分板块标的详见 `knowledge/watchlist-sectors.md`*

### Recommended Additional Data Sources

| Channel | What It Provides |
|---------|-----------------|
| **NewsAPI** | Aggregated headlines from 80K+ sources — newsapi.org |
| **Finnhub** | Real-time quotes, earnings calendar — finnhub.io |

## Daily Workflow

When asked to collect daily news (`/loop` or manual run):

### ⚠️ 强制执行规则
1. **每个step都必须执行**，无论是否假期、休市或数据有限。假期时技术指标用最新可用数据，新标的发掘和供应链扫描不依赖实时行情。
2. **开始workflow前必须用TodoWrite构建完整的21步任务清单**，每完成一步标记completed再进入下一步。禁止跳过任何步骤。
3. 如果某步因客观原因（如API限流）无法完成，在TodoWrite中标注原因，但仍需尝试替代方案（如WebSearch替代Exa）。
4. **Exa等搜索工具触发速率限制时必须等待冷却（60-120秒）后重试**，不得跳过或留到下次session补跑。完整性 > 执行速度。Bash `sleep 90 && echo done`即可。
5. **市场状态验证**：用户时区为UTC+8（北京时间）。判断A股/港股是否开盘/收盘前，必须先用 Bash `date` 确认当前BJT时间，并用 Yahoo Finance `marketState` 字段交叉验证：
   - `REGULAR` = 交易中
   - `POSTPOST` = 已收盘（有当日收盘价）
   - `PREPRE`/`PRE` = 未开盘（**Yahoo返回的"日内数据"实为上一交易日的历史值**，必须标注为stale，不可作为今日数据采信）
   - A股交易时间：9:30-11:30 + 13:00-15:00 BJT；港股9:30-12:00 + 13:00-16:00 BJT
6. **News agent返回数据需交叉验证**：subagent返回的"今日已收盘"或"未来时间点"市场数据必须用 Yahoo Finance `marketState` + `regularMarketTime` 字段验证。如marketState=PREPRE但agent给出"已收盘价"，则该数据必为projected/futures contract，标记为"⚠未验证"，不写入持仓盈亏计算。

### Phase 1: Context Loading (do this FIRST)
1. **Load knowledge base** — Read `knowledge/context.md`, `knowledge/ai-landscape.md`, and `knowledge/watchlist-sectors.md` to understand current world state, AI industry map, and tracked sectors/tickers
2. **Load open positions** — Read `decisions/positions.md` and the last 2-3 daily decision logs to understand active trades and recent signals
3. **Identify follow-ups** — Note which open positions need price updates, stop-loss/take-profit checks, and which watchlist items may have triggered

### Phase 2: Data Collection
4. **Extract prices** — Use Yahoo Finance for indices, commodities, forex. Use Alpha Vantage for technical indicators (RSI, MACD, BBANDS) on key positions, commodity spot prices, and news sentiment scores
5. **Check positions** — Compare current prices against open position stop-loss and take-profit levels. Flag any triggers
6. **Search news** — Use Exa with the minimum query set below; search in **both English and Chinese**
7. **Fetch details** — Use Exa fetch or Playwright for paywalled/JS-heavy articles that seem high-impact
8. **Pull macro data** — Use FRED for any new US economic releases (CPI, NFP, GDP, etc.)

### Phase 3: Analysis & Output
9. **Write report** — Structured daily briefing in `reports/YYYY-MM-DD.md` (Chinese 中文). Include a "与昨日相比的变化" summary and a dedicated "AI与科技" section. All report content in Chinese; keep ticker symbols, financial terms (P/E, SAAR, WTI etc.) in English. **每天只产出一个报告文件**，所有深度研究（板块分析、新标的发掘、技术指标等）直接写入主报告的对应section，不要生成单独的中间文件（如 `*-deep-dive.md`、`*-discoveries.md`）。
10. **Generate draft signals** — Draft trading signals with reasoning, plus follow-up on all prior open signals
11. **Supply chain bottleneck scan** — Check AI supply chain for emerging bottlenecks and lagging sectors:
    - **瓶颈轮动规律**: GPU → 存储/HBM → 电力/变压器 → 液冷散热 → PCB/材料 → 封装
    - Compare 52-week gains across supply chain segments to identify relative laggards
    - Check for supply shortage news (交付周期延长, 订单排满, 涨价) in under-covered areas
    - Look for A-share/HK equivalents when US supply chain stocks surge
    - **产业链下钻分析**: 当某个板块涨幅显著时，不要停留在板块级别。拆解到子环节（芯片→封装→器件→模块→设备→测试→材料），对比各子环节涨幅，找出被忽视的细分。例如光模块板块不应只看中际旭创，还要看上游光芯片（长光华芯）、测试设备（联讯仪器）、光器件（天孚通信）、光纤光缆（亨通光电）等
    - **产业集群效应**: 关注同城/同园区公司联动（如苏州光子产业集群），龙头爆发后扫描其上下游和同区域关联公司
12. **Devil's advocate review** — Before finalizing any signal, explicitly challenge it:
    - **反面论证**：这个判断可能错在哪里？有什么我忽略的风险？
    - **数据矛盾**：是否有相反方向的数据点被低估了？
    - **时机风险**：趋势是否已被充分定价？是否在追高？
    - **历史类比**：类似情景历史上的结果如何？
    - For each signal, write a short "反方观点" (bear case / counterargument) in the decision log. If the counterargument is stronger than the thesis, downgrade or drop the signal.
13. **Technical indicator analysis（深度研究必做）** — For every candidate stock, analyze technical indicators before entry:
    - Pull 6-month daily historical data via Yahoo Finance (`get_historical_stock_prices`, period=6mo)
    - Calculate: **MA20/MA60**（趋势方向+金叉/死叉）, **RSI14**（超买>70/超卖<30）, **MACD** DIF/DEA/柱状体（动能方向）, **布林带%B**（波动位置）
    - A股标的(.SS/.SZ)需手动计算（Alpha Vantage不支持A股技术指标）
    - **入场规则**: RSI>70不追高等回调; 价格低于MA20+MA60双线=趋势偏空,谨慎入场; MACD死叉+柱放大=下跌动能增强,等柱缩窄; 布林%B<20=超卖区,可能是底部
    - 技术面不改变基本面判断方向，但决定入场时机。Kelly给仓位大小，技术面给入场时点
14. **Fundamental deep dive（基本面深度研究）** — 对每个候选标的（Kelly为正或进入关注清单的），系统性分析以下6个维度：
    - **A. 财报分析**
      - Yahoo Finance `get_financial_statement`：最近2-3个季度的income_stmt + balance_sheet + cashflow
      - 关注：营收增速、毛利率变化、经营现金流、资产负债率
      - 红旗：营收增长但现金流恶化、应收账款暴增、有息负债快速攀升
    - **B. 估值与市场预期**
      - Yahoo Finance `get_stock_info`：PE/PB/PS、市值、52周高低、分析师目标价
      - Yahoo Finance `get_recommendations`：券商评级变化（近6个月）
      - 与同板块标的横向对比PE/PB，识别估值溢价或折价
    - **C. 股东与资金动向**
      - Yahoo Finance `get_holder_info`：机构持仓变化、前十大股东、内部交易
      - 关注：机构增持/减持趋势、大股东质押比例、高管减持
    - **D. 合作方与供应链定位**
      - Exa搜索："[公司名] 客户 供应商 合作"、"[公司名] 供应链"
      - 绘制关键客户/供应商关系
      - 评估客户集中度风险（单一大客户占比>30%标注警告）
    - **E. 竞争格局与护城河**
      - Exa搜索："[公司名] 竞争对手 市占率"、"[板块] 竞争格局"
      - 识别护城河类型（技术壁垒/客户粘性/规模效应/牌照/专利数量）
      - 评估替代风险（技术路线变化对该公司的威胁）
    - **F. 政策催化与风险**
      - Exa搜索："[板块] 政策 补贴 规划"
      - 识别即将到来的催化事件（财报日期、行业展会、政策发布窗口）
      - 评估政策风险（监管收紧、出口管制、行业整治）
    - 输出：每个标的生成"基本面摘要"写入decision log，包含6维度关键发现+一句话结论（利好/中性/利空）
15. **Data validation（数据验证）** — 启动独立验证subagent（`run_in_background: true`），交叉验证本次session所有关键数据：
    - 用Agent工具启动，prompt中列出所有需要验证的数据点（参见下方 Data Validation Agent Prompt Template）
    - 验证维度：价格/估值准确性、财报数据一致性、新闻事实真实性、供应链关系可信度、数据时效性
    - Agent使用Yahoo Finance重新拉取价格/财报、Exa二次搜索验证事实声明
    - 验证结果分三级：✓已验证、⚠存疑/修正、✗错误/过时
    - **在finalize signals之前必须review验证结果**，对✗项修正，对⚠项在信号中标注不确定性
16. **Finalize signals** — Only signals that survive the devil's advocate review AND technical indicator check AND fundamental deep dive AND data validation get logged as positions
17. **Low-price alternative scan** — For every signal with stock price >¥40 or 52-week gain >200%, actively search for cheaper alternatives:
    - **同链条替代**: 在同一供应链环节寻找市值更小、股价更低（¥30以下优先）、涨幅更小的标的
    - **上游/材料端**: 龙头已被充分定价时，检查其上游原材料/零部件供应商是否被忽视
    - **港股折价**: 检查是否有港股对应标的存在严重估值折价（如PE差5-10倍）
    - **估值过热筛查**: 52周涨幅>200%自动标注"已充分定价风险"，优先推荐涨幅<100%的滞后标的
    - **Exa专项搜索**: 中文搜索"低估值 被忽视 [板块关键词]"发掘市场未充分关注的标的
18. **New stock discovery（必做）** — 每次研究session必须拓展新标的，不能只分析watchlist已有的公司：
    - 对每个重点板块，用Exa搜索"[板块关键词] 新股 次新股"、"被忽视 低估值 [板块]"、"上游材料 [板块]"
    - 发现新公司后用Yahoo Finance验证价格/PE/52周涨幅
    - 符合条件的（¥30以下优先、52周涨幅<100%、逻辑清晰）加入watchlist-sectors.md
    - 每次session至少新增3-5个此前未跟踪的标的
19. **Track decisions** — Log to `decisions/YYYY-MM-DD.md` (include both thesis and 反方观点) and update `decisions/positions.md`
20. **Update knowledge** — Update knowledge docs ONLY when state actually changes (see Knowledge Update Triggers below)
21. **Record prompt improvements** — If during this session any workflow gaps, missing steps, or methodology improvements were identified, add them to `knowledge/prompt-evolution.md` for future CLAUDE.md updates

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
| 7 | — | `液冷 变压器 光模块 PCB 先进封装 AI算力` | AI supply chain (A-share focused) |
| 8 | `AI data center power cooling storage bottleneck` | — | AI supply chain bottlenecks |
| 9 | — | `低估值 被忽视 AI算力 供应链 港股折价` | Undervalued / overlooked plays |

### Data Freshness Rules
- **用户时区**：UTC+8（北京时间）。所有"今日/明日"判断以BJT为准，先用 `date` 命令确认。
- **市场交易时间（BJT）**：A股 9:30-11:30 + 13:00-15:00；港股 9:30-12:00 + 13:00-16:00；美股21:30-04:00（夏令时）
- **US market data**: prior trading day's close (US markets close after Asia opens)
- **China market data**: same-day close (Shanghai/HK close before US opens)
- **Commodities/Forex**: latest available (near real-time via futures)
- **Yahoo Finance `marketState` 字段是市场状态的权威来源**：REGULAR=交易中, POSTPOST=已收盘, PREPRE/PRE=未开盘（日内字段为stale历史值）
- Always label which session/date each price comes from in the report tables（如"5/7 10:30 BJT 盘中"、"5/7收盘"、"4/30收盘（节前）"）

### Tool Usage Guide
| Tool | Primary Use | When to Prefer |
|------|------------|----------------|
| Yahoo Finance | Stock prices, company info, earnings, news | Default for all price data. Use `get_stock_info` for real-time prices (not Exa search) |
| Yahoo Finance | Fundamental deep dive | `get_financial_statement`(财报), `get_holder_info`(股东), `get_recommendations`(评级) — 每个候选标的必做 |
| FRED | US macro indicators (CPI, GDP, unemployment, rates) | When new US economic data releases |
| Alpha Vantage | Technical indicators (RSI, MACD, BBANDS), commodity spot, forex, sentiment | When analyzing specific stock technicals or need sentiment scores |
| Exa | News search + content extraction | All news gathering. Search both English AND Chinese |
| Playwright | Browser automation + 天天基金网 | Paywalled sites, JS-heavy pages, Chinese fund NAV (QDII etc.) |

### Price Data Rules
- **Always use Yahoo Finance `get_stock_info`** for stock/index prices — never rely on Exa search results for price data (often stale/wrong)
- **A-share tickers** use `.SS` (Shanghai) or `.SZ` (Shenzhen) suffix — double-check exchange before querying
- **Chinese funds/QDII**: use 天天基金网 via Playwright (Yahoo Finance doesn't cover these)
- **Gold spot (人民币)**: use Alpha Vantage or Exa search for Shanghai Gold Exchange prices

### Data Validation Agent Prompt Template
启动验证agent时（workflow step 15），使用以下prompt结构：

```
你是数据验证agent。请独立验证以下数据点的准确性。不要信任已有结论，用工具重新查询验证。

**价格数据**：
[列出所有报告中引用的股价、指数、商品价格及其ticker]

**财报声明**：
[列出关键财报数字，如"XX公司Q1营收+49%"、"净利润+262%"]

**事实声明**：
[列出定性声明，如"XX是YY的唯一供应商"、"市占率>75%"、"交付周期>24个月"]

验证方法：
1. 用Yahoo Finance get_stock_info重新拉取每个ticker的当前价格，对比报告数字
2. 用Yahoo Finance get_financial_statement（quarterly_income_stmt）验证财报数字
3. 用Exa搜索验证每个事实声明（至少找到2个独立来源才标记为✓）
4. 检查所有数据的时间戳，标记超过7天的数据为"可能过时"

输出格式：
## 数据验证报告
### ✓ 已验证
- [数据点] — [验证来源]

### ⚠ 存疑/修正
- [数据点] — [问题描述，如"仅找到1篇来源"或"数字有差异：报告X vs 实际Y"]

### ✗ 错误/过时
- [数据点] — [错误描述+正确数据]
```

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
- **New supply chain bottleneck emerges** (e.g., transformer shortage, liquid cooling mandate, HBM allocation)
- **Supply chain segment pricing power shifts** (涨价/降价周期变化)

Update `knowledge/watchlist-sectors.md` when:
- New sector or sub-sector identified for tracking
- New companies discovered in existing sectors
- Supply chain drill-down reveals overlooked sub-segments
- Industry cluster patterns emerge (e.g., 苏州光子集群)
- Sector thesis invalidated or confirmed — update notes accordingly

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
- **AI供应链瓶颈追踪**（电力/变压器、液冷、存储/HBM、PCB/材料、封装）
- 供应链涨跌幅对比，标注滞后板块

## 关键风险与关注清单
- ...

## 操作建议 — 中国股票持仓信号

**投资风格：中长期持仓，非短线交易。** 不做隔日买卖，最短持仓周期为1个月。

### 短期持仓（1-3个月）
| 操作 | 标的 | 入场逻辑 | 目标/止损 | 信心 | 催化剂/退出条件 |
|------|------|----------|-----------|------|-----------------|
| 买入/持有/回避 | 板块或代码 | 原因 | 目标价/止损价 | 高/中/低 | 什么会改变判断 |

### 中期持仓（3-6个月）
| 操作 | 标的 | 入场逻辑 | 目标/止损 | 信心 | 关键假设 |
|------|------|----------|-----------|------|----------|
| 买入/持有/回避 | 板块或代码 | 原因 | 目标价/止损价 | 高/中/低 | 逻辑成立的前提条件 |

### 长期配置（6-12个月+）
| 操作 | 标的 | 投资逻辑 | 信心 | 结构性趋势 |
|------|------|----------|------|------------|
| 配置/增持/减持/回避 | 板块或代码 | 原因 | 高/中/低 | 支撑该判断的长期趋势 |

### 重点关注板块
*详见 `knowledge/watchlist-sectors.md` — 涵盖AI供应链全链条（芯片→光模块→液冷→变压器→PCB→封装→存储）及非AI板块（新能源车、银行、地产、消费等）。*

### 信号框架
**核心原则：寻找中长期趋势性机会，忽略日内波动噪音。** 每日报告追踪市场变化，但信号着眼于周/月级别的趋势。

信号由以下维度综合得出：
1. **宏观趋势**：美联储政策周期方向、美元/人民币中期走势、中美贸易关系演变
2. **中国结构性变化**：央行政策周期、财政刺激力度、产业政策方向、监管基调转向
3. **资金流向趋势**：北向资金持续流入/流出、板块轮动方向、机构持仓变化
4. **估值与基本面**：板块估值分位、盈利增长趋势、股息率
5. **地缘政治风险溢价**：中美关系阶段性变化、制裁升级/缓和周期
6. **AI供应链瓶颈轮动**：瓶颈从GPU→存储→电力/液冷→PCB/封装依次传导，关注美股供应链龙头暴涨后的A股映射标的（如美光暴涨→A股存储映射；VRT暴涨→A股液冷映射）

### 仓位管理 — Kelly公式
对每个新信号，使用Kelly公式量化仓位大小，避免拍脑袋分配资金：

```
赔率 b = (目标价 - 当前价) / (当前价 - 止损价)
Kelly f* = (胜率p × 赔率b - 败率q) / 赔率b
实际仓位 = 半Kelly = f* / 2（降低波动）
```

- **赔率 b > 2**：风险回报优秀，可用半Kelly仓位
- **赔率 1 < b < 2**：一般，需高胜率(>55%)才值得
- **赔率 b < 1 或 Kelly为负**：不下注，等更好入场价
- **胜率估计**：逻辑直接+估值合理=55%；不确定性较大=50%；催化剂较远=45%
- **最小有意义仓位**：¥3,000。Kelly算出低于此金额的标的，要么不买，要么等条件改善
- 每个信号表格增加"赔率"和"Kelly仓位"列

### 重要声明
以上信号仅供信息参考和教育用途，不构成投资建议。投资前请自行研究并评估风险承受能力。
```

## File Structure

```
daily-news/
├── CLAUDE.md                    # System prompt: 方法论+流程+引用规则（不含动态数据）
├── knowledge/                   # Living knowledge base (动态数据集中管理)
│   ├── context.md               # Global macro/geopolitical/market state
│   ├── ai-landscape.md          # AI industry map, key players, supply chain, ticker reference
│   ├── watchlist-sectors.md     # Tracked sectors, sub-chains, representative companies & tickers
│   └── prompt-evolution.md      # System prompt改进日志：待处理/已完成的CLAUDE.md修改要点
├── reports/                     # Daily briefing reports (中文)
│   └── YYYY-MM-DD.md            # Chinese version (中文版)
├── decisions/                   # Trading decision memory system
│   ├── positions.md             # Current open positions & watchlist (living document)
│   ├── YYYY-MM-DD.md            # Daily decision log
│   └── review.md               # Weekly/periodic review of signal accuracy
├── tools/                       # Python calculation utilities
│   ├── technical.py             # MA/RSI/MACD/BB/ATR — CLI: python tools/technical.py <price_file.json>
│   ├── kelly.py                 # Kelly formula position sizing — CLI: python tools/kelly.py <price> <target> <stop> <winrate>
│   └── save_prices.py           # Price data freshness check — CLI: python tools/save_prices.py --check
├── data/
│   └── prices/                  # Historical price JSON files (7-day expiry)
│       └── YYYY-MM-DD.json      # Yahoo Finance data, standard format with metadata
└── sources.md                   # Tracked sources and RSS feeds
```

## Knowledge Base System

The knowledge base (`knowledge/`) is a set of **living documents** that accumulate understanding across sessions. Unlike daily reports (snapshots of one day), knowledge docs represent **the current state of the world** and are updated incrementally.

### `knowledge/context.md` — Global Context
Sections: Geopolitical State, US Economic State, China Economic State, US-China Relations, Market Regime. Updated after each daily report with any state changes.

### `knowledge/ai-landscape.md` — AI Industry Map
Sections: US AI Leaders, China AI Leaders, Chip Supply Chain, AI Storage/Memory, AI Regulation, US-China AI Rivalry, Investment Themes, Global AI Ticker Reference. Updated when major AI developments occur.

### `knowledge/watchlist-sectors.md` — Sector Watchlist & Targets
AI supply chain sub-sectors (chips, optical, cooling, power, PCB, packaging, storage) and non-AI sectors, each with representative companies and tickers. Updated when new sectors/companies are discovered or supply chain dynamics change.

### `knowledge/prompt-evolution.md` — System Prompt Evolution Log
Records improvement ideas for CLAUDE.md discovered during daily sessions. When the user requests a system prompt update, **read this file first** and batch-process pending items. Each entry has a type, priority, and source. Implemented items are archived with dates. This ensures no insight is lost between sessions.

### How to Use Knowledge Base
1. **Start of session**: Read all `knowledge/` files instead of re-reading past daily reports
2. **After daily report**: Update knowledge docs with any state changes (e.g., if PBOC cuts rates, update China Economic State)
3. **New discoveries**: Add new companies/sectors to knowledge docs, NOT to CLAUDE.md
4. **Key principle**: Knowledge docs answer "what is the current state?" while daily reports answer "what happened today?" CLAUDE.md answers "how to analyze?"

## Memory & Decision Tracking System

### 1. Daily Decision Log (`decisions/YYYY-MM-DD.md`)
Created alongside each daily report. Records:

```markdown
# 决策日志 — YYYY-MM-DD

## 今日发出的信号
### 短期（1-3个月）
| # | 操作 | 标的 | 入场价格 | 逻辑 | 反方观点 | 目标/止损 | 信心 | 状态 |
|---|------|------|----------|------|----------|-----------|------|------|

### 中期（3-6个月）
| # | 操作 | 标的 | 入场价格 | 逻辑 | 反方观点 | 目标/止损 | 信心 | 状态 |
|---|------|------|----------|------|----------|-----------|------|------|

### 长期（6-12个月+）
| # | 操作 | 标的 | 入场价格 | 逻辑 | 反方观点 | 关键假设 | 信心 | 状态 |
|---|------|------|----------|------|----------|----------|------|------|

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
### 短期（1-3个月）
| 开仓日期 | 标的 | 操作 | 入场价 | 当前价 | 盈亏 | 止损 | 止盈 | 状态 | 备注 |
|----------|------|------|--------|--------|------|------|------|------|------|

### 中期（3-6个月）
| 开仓日期 | 标的 | 操作 | 入场价 | 当前价 | 盈亏 | 止损 | 止盈 | 状态 | 备注 |
|----------|------|------|--------|--------|------|------|------|------|------|

### 长期（6-12个月+）
| 开仓日期 | 标的 | 操作 | 入场价 | 当前价 | 盈亏 | 关键假设 | 状态 | 备注 |
|----------|------|------|--------|--------|------|----------|------|------|

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
