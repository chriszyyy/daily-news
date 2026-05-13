# Daily News Intelligence Hub

## Purpose

This project collects, organizes, and analyzes daily news to generate **actionable trading signals for China stocks (A-shares, Hong Kong)**. All news and data collection serves one end goal: **should I buy, sell, hold, or avoid specific China stock sectors/indices today?**

Four information pillars feed the analysis:

1. **US Economy & Markets** — Fed policy, inflation, jobs, earnings, trade policy — because US macro directly impacts China markets
2. **China Focus** — China's economy, trade data, PBOC policy, stimulus, regulatory changes, property market, tech sector
3. **Global Geopolitics** — US-China tensions, tariffs, sanctions, conflicts — the biggest risk factor for China stocks
4. **AI & Technology** — AI breakthroughs, chip supply chain, US-China AI rivalry, AI regulation — the defining investment theme of this era

## 🎯 Skill Index — 何时调用什么

本项目所有可执行流程封装为 skill，存放在 `.claude/skills/`。请优先调用 skill 而不是重新实现：

| 触发场景 | 调用 skill |
|---------|-----------|
| "做今日简报" / `/loop` / 生成 reports/YYYY-MM-DD.md | `daily-briefing` |
| **任何新信号生成 / 加减仓 / 卖出决策（4 道闸 pipeline）** | **`signal-generation`** ⭐ |
| 单标的研究 / 产业链下钻 / 供应链扫描 / 信号 Gate 3 子调用 | `bottleneck-analysis` |
| "深度研究 XX 公司" / 候选标的进入 watchlist | `fundamental-deepdive` |
| Session 末尾验证数据 / 用户质疑数据准确性 | `data-validation` |
| 板块扫描 / "找便宜替代" / 拓展 watchlist | `discover-new-stocks` |
| 任何 MCP 工具失败 / 限流 / 超时 | `tool-fallback` |
| **daily-briefing 末尾自检** | **`briefing-audit`** ⭐ |

**用 Skill tool 调用**，例如：`Skill(skill="daily-briefing")`。

### 🔴 强制调用规则（防"软跳过"）

1. **任何写入决策日志的信号必须先走 `signal-generation` 4 道闸** — 缺 Gate 视为信号未入库
2. **`daily-briefing` 必须以 `briefing-audit` 结束** — audit FAIL 项必须修正后才结束 session
3. **每个 skill 头部声明 Contract（Triggers/Inputs/Outputs/Calls/Called by）** — 子 skill 之间依赖显式化

## 🚫 NO GUESSING — 数据准确性硬约束

**所有数字(价格 / 持仓 / 现金 / 财报 / 涨跌幅 / 仓位占比)必须来自实测或用户确认,严禁猜测或推算。**

### 强制规则
1. **价格 / 财报 / 估值** — 必须 Yahoo Finance MCP 直接拉取,标注时间戳;不能用"估"、"约"、"差不多"
2. **持仓 / 现金 / 成本价** — 必须从 `decisions/positions.md` 读取,或用户主动提供;**绝不基于历史推算当前余额**
3. **涨跌幅 / 浮盈** — 必须 (现价 - 成本价) / 成本价 实算;不可以"看起来差不多"
4. **遇到不一致** — 立即问用户(用 AskUserQuestion 或直接问),**不要猜测哪个是对的**
5. **历史数据可能过时** — 所有从历史文件读出的数字默认"待验证",用户确认前不当作真实

## 🕐 数据新鲜度强制门(每次响应前必检)

**触发**:每次涉及"持仓 / 价格 / 涨跌幅 / 信号"的响应前。

### 必检 3 步
1. **`Bash date`** 拿当前 BJT — 不能凭印象,必须每次跑
2. **对比上次拉数据的时间戳** — 超 30 分钟 / 跨越市场状态(开盘/午休/收盘)→ 必须重拉
3. **检查 Yahoo `marketState`** — PREPRE / REGULAR / POSTPOST,字段不一致重拉

### A 股时点(BJT)
- <09:30 PREPRE(昨收 stale)
- 09:30-11:30 REGULAR 上午盘中
- 11:30-13:00 午休(11:30 数据)
- 13:00-15:00 REGULAR 下午盘中
- 15:00-15:15 POSTPOST 切换中
- **>15:15 POSTPOST 当日收盘价**

### 反模式(严禁)
- ❌ "之前已经拉过了" — 跨越市场状态必须重拉
- ❌ 用 12:39 午盘数据回答 15:40 用户提问
- ❌ 写"BJT 12:39"不跑 `Bash date` 验证
- ❌ "估算占比约 57%" / "可能在 ¥10-15 之间" / "黄金大概 ¥83K"
- ❌ 基于历史推算当前余额("之前透支 ¥1,145 → 现在应该是 ¥X")

### 正确做法
- ✅ 用户问"现在如何" → `Bash date` → 看 marketState → 决定重拉
- ✅ 收盘后(>15:15)写报告必拉**收盘价**,不复用盘中数据
- ✅ 每个数字标"X 时 X 分 marketState=XXX 实测"
- ✅ 不确定就问用户,不猜

### 触发条件汇总
- 任何用户决策依赖的数字 → 必须实测 / 确认 + 必须新鲜
- 任何写入 positions.md / decisions/ / reports/ 的数字 → 同上
- 计算仓位占比 / 浮盈 / 总市值 → 显式列出每个分子分母

## 🎭 Playwright 强制 Fallback(Yahoo stale 必抢实时)

**触发**(命中任一立即 Playwright,不要"warning 后继续用 stale"):
1. **时点矛盾**:Yahoo `regularMarketTime` 转 BJT 后**比当前 `Bash date` 落后 >15 分钟** 且 `marketState=REGULAR`
2. **盘后未刷收盘**:BJT >15:15 但 Yahoo 仍返回 `marketState=REGULAR` 或盘中价
3. **跨越市场分界 stale**:午休前→下午盘、下午盘→收盘 跨越后 Yahoo 没更新
4. **Volume 异常低**:成交量明显小于历史日均(说明只截到半天数据)
5. **用户明说"开盘了"/"收盘了"** 但 Yahoo 数据时点对不上
6. **任何 MCP 工具返回空/错/限流** — 直接 Playwright,不要"等会再试"

### A 股实时数据源(优先东方财富)
1. **东方财富**(首选):
   - 沪市:`https://quote.eastmoney.com/sh{code}.html`(如 sh600378)
   - 深市:`https://quote.eastmoney.com/sz{code}.html`(如 sz000001)
   - **抓 `<title>` 标签直接拿到"最新价 涨跌(涨幅%)"** + 表格抓五档/高低/量比/PE
2. **新浪财经**:`https://finance.sina.com.cn/realstock/company/sh{code}/nc.shtml`
3. **腾讯财经**:`https://gu.qq.com/sh{code}`

### 港股 / 美股 / 商品实时数据源
- 港股:东方财富 `https://quote.eastmoney.com/hk/{5位代码}.html`
- 美股:东方财富 `https://quote.eastmoney.com/us/{TICKER}.html` 或 Google Finance
- 黄金人民币:上海金交所 `https://www.sge.com.cn/`
- 美国宏观:FRED 失败 → `https://fred.stlouisfed.org/series/{ID}`

### 🔴 用完必关闭浏览器(资源管理硬规则)
- **每个 Playwright 任务结束 → 立即调用 `mcp__playwright__browser_close`**
- 一个对话最多保持 **1 个 tab 活跃**,多个查询用完一个关一个再开下一个
- 用户不会问"为什么 Chrome 没关",但残留 Chrome 进程占内存 → 必须自觉关
- **反模式**:
  - ❌ 拉完数据继续聊别的,不关浏览器 — 残留进程
  - ❌ 同时开 5 个 tab 拉 5 只股票 — 串行 + close,不要并行 tab
  - ❌ "用户可能还要看",留着浏览器 — 不要预判,要看再开

### 反模式(严禁)
- ❌ "Yahoo 数据时点不对,我先按上午盘数据给建议" — 实时决策必须实时数据
- ❌ "我大约 30 分钟后再拉一次" — 用户在等当下决策,不能拖
- ❌ 警告"数据可能 stale"但仍基于 stale 数据下结论 — 警告不等于免责
- ❌ Playwright 拉完数据忘了 `browser_close` — 浪费用户机器资源

### 正确做法
- ✅ 检测到 stale → 立即 `browser_navigate` 到东财 → `browser_evaluate` 抓 DOM → 标"东方财富 BJT XX:XX 实测" → **`browser_close`** → 给建议
- ✅ Playwright 也失败 → 明确告诉用户"两个源都拿不到实时,建议用券商 APP 自己看"

### Why
2026-05-13 13:07 案例:用户说"下午开盘了",Yahoo 返回 `regularMarketTime` 对应 BJT 11:43 午休前快照(stale 84 分钟),但 marketState=REGULAR。我若用此数据回答"昊华是否撤单"会给错决策建议。Playwright 抓东财页面 title 直接拿到 "昊华科技 33.37 0.07(0.21%)"实时价 + 五档盘口,决策才有依据。

## 💰 P&L 术语严格区分(防止"累计 vs 当日"混淆)

**触发**:任何写浮盈/盈亏/贡献的语境。

### 3 个术语必须严格区分,不能混用

| 术语 | 公式 | 含义 |
|---|---|---|
| **累计浮盈** | (今日收 - **成本价**) × 持股 | 从开仓到现在赚了多少(含历史) |
| **当日浮盈变化** | (今日收 - **昨日收**) × 持股 | 今天一天市值变了多少 |
| **已实现** | (卖出价 - 成本价) × 卖出数 | 卖出锁定的盈亏(独立于浮盈) |

### 反模式(严禁)
- ❌ 写"当日贡献 +¥X" 但实际用的是"累计浮盈 + 已实现"公式 — 混淆用户对当天表现的理解
- ❌ 持仓首日把"累计浮盈"当"当日浮盈"算 — 实际两者相等不需区分,但仍要标明
- ❌ 把"已实现"塞进"浮盈"里 — 已实现是落袋,浮盈是账面

### 正确做法
- ✅ 标题写"截至 5/12 收盘 累计浮盈合计"或"5/12 当日净赚"二选一,不能模糊
- ✅ 当用户问"今天赚了多少"→ **默认给当日浮盈变化**,顺带提累计
- ✅ 持仓总览段:同时给"累计浮盈"和"当日浮盈变化"两栏,避免歧义

### Why
2026-05-12 案例:报告写"当日总贡献 +¥1,314"实际是"5/6 开仓至今累计浮盈 +¥1,070 + 5/12 已实现 +¥244",真正的 5/12 当天净赚仅 +¥491。用户问"怎么算的"才发现混淆。

## 🗂 单一事实源(SSOT)— 防文档漂移

**核心原则**:**每个数据点只在一个文件中维护**,其他文件**禁止重复存储**,只能引用。

### 数据归属表(谁是 source of truth)

| 数据类型 | 唯一源 | 其他文件如何处理 |
|---|---|---|
| **持仓数量 / 成本价 / 当前价 / 浮盈** | `decisions/positions.md` | 其他文件**只写"详见 positions.md"**,严禁复制价格 |
| **现金余额** | `decisions/positions.md` 头部 | 同上 |
| **每日操作信号 + 4 道闸输出** | `decisions/YYYY-MM-DD.md` | reports/ 只写摘要,链接到决策日志 |
| **课题进展 + 候选标的逻辑** | `research/topicXX.md` | INDEX.md 只列状态行,不复制详情 |
| **板块逻辑 / 子链分类** | `knowledge/watchlist-sectors.md` | research/ 只引用,不复制 |
| **AI 产业图谱** | `knowledge/ai-landscape.md` | 同上 |
| **宏观状态 / 关键催化** | `knowledge/context.md` | reports/ 引用日期戳,不复制 |
| **方法论 / 流程** | `.claude/skills/*` | CLAUDE.md 只放索引 |

### 📌 价格写入硬规则

**任何文件写持仓股票的"当前价"或"涨跌%" → 必须满足 1 个**:
1. 该文件本身就是 source of truth(positions.md 或当日 decisions/YYYY-MM-DD.md)
2. **明确标注时间戳**:`¥X.XX (5/12 收 POSTPOST 实测)` — 防止后续看时不知道何时拉的
3. 否则只写 `[价见 positions.md]` 或不写

**反模式(严禁)**:
- ❌ `watchlist-sectors.md` 写"国茂 ¥17.72 已建仓" — 价格会过期且不会自动更新
- ❌ `research/INDEX.md` 写"国茂 ¥17.65" — 5/8 价格停在 5/8
- ❌ research/topicXX.md 写"现价 ¥17.65" — 调研当天的价格冻结后误导未来读者

### ✅ 正确做法

- **持仓信息**:research/INDEX.md 只标"已建仓 ✅(详见 positions.md)",**不写价格**
- **板块标的**:watchlist-sectors.md 可写"5/8 调研价 ¥17.65" + **明确日期戳**,但不能伪装成"当前价"
- **课题快照**:research/topicXX.md 写"调研日 5/10 现价 ¥17.65" 永远冻结,不更新
- **当前价**:**永远去 positions.md 查**,其他文件只引用

### Why
2026-05-12 国茂案例:同一标的价格散落 8 个文件 — `positions.md ¥17.58` ✓ / `watchlist ¥17.72` (5/11 stale) / `INDEX ¥17.65` (5/8 stale) / `topic06 ¥17.65` (5/8 stale)。如果 daily-briefing 加载到 watchlist 或 INDEX 的价格,信号生成会基于错误数据。

### 强制点
- `daily-briefing` P1.1 加载 knowledge/* 时:**只读逻辑/分类,价格全部去 positions.md 取**
- `briefing-audit` 新增 Check 6:**grep 所有文件中持仓标的价格,与 positions.md 对比**,不一致 → 🔴 FAIL
- 写入 watchlist/INDEX/research 时:**价格必须带日期戳冻结**,否则不写价

## 📊 "滞涨/认知差" 标签强制 4 维校验

**触发**:任何标的被贴上"滞涨"、"认知差"、"未被定价"、"被市场忽视"标签时。

### 必报 4 维数据(缺一不可)
1. **52w 涨幅%** + **52w 区间分位**(现价距高 -X%、距低 +Y%)
2. **近 20 日涨幅%**(月度位置)
3. **近 5 日涨幅%**(周度启动信号)
4. **是否有近期放量跳涨**(单日 5%+ + 量能 ≥2x 均量 = 启动信号)

### 取消"滞涨"判定的硬阈值
任一指标命中 → **必须取消"滞涨/认知差"标签**:
- 近 5 日 >10%
- 近 20 日 >15%
- 距 52w 高 <15%
- 近 5 个交易日内任一日 +5% 且量能 ≥2x 均量

→ 改为"**业绩硬+已启动的常规中线**",赔率重新计算(从 ≥3x 压到 ≤2x)

### 反模式(严禁)
- ❌ 只看"52w +5%" 就标"滞涨" — 一年前可能也是高位
- ❌ 不报"距 52w 高的距离" — 隐藏追高位置
- ❌ 没看近 5/20 日动量 — 可能正处于"启动后 1-2 周"的最差买点

### Why
2026-05-12 国茂 603915 案例:被标"52w +5% 滞涨认知差" → 用户 ¥17.75 建仓 → 复核发现近 20 日 +15.3%、5/8 放量跳涨 +7.4%、距 52w 高仅 -10% — 实际是**追在启动后第二天**,赔率从"5x/1x"压缩到"1.4x/1.5x"。

### 强制点
- `daily-briefing` P3.1 瓶颈扫描:每个候选必报 4 维
- `signal-generation` Gate 1 技术面:4 维不全 → Gate 1 ✗
- `fundamental-deepdive` 6 维度:位置维度强制包含 4 维
- `discover-new-stocks`:发现新标的时必带 4 维数据,不带 = 标的不入 watchlist


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
- **China Policy**: PBOC decisions, stimulus measures, regulatory changes
- **US-China Relations**: tariffs, sanctions, tech restrictions, diplomatic developments, Taiwan
- **China Markets**: Shanghai Composite (000001.SS), Hang Seng (^HSI), CSI 300, A-shares
- **China Trade**: export/import data, Belt & Road, trade partners, supply chain shifts
- **China Domestic**: tech sector regulation, property crisis, local government debt, demographics
- **CNY/USD**: yuan exchange rate movements and PBOC intervention signals
- **Search Sources**: Exa search 中英文 — 中文关键词如 中国经济, 贸易战, 关税, 人民币, A股, 央行

### Global Geopolitics
- Russia/Ukraine, Middle East, EU politics
- Trade wars, sanctions, tariffs (beyond US-China)
- Elections and government transitions worldwide
- Military/defense developments
- International organizations (UN, NATO, G7/G20, BRICS, SCO)

### AI & Technology Focus
- **AI模型与突破**: 美国/中国领先实验室的模型发布、基准测试、能力突破
- **AI基础设施/芯片**: GPU、AI加速器、芯片代工、芯片出口管制
- **AI存储/HBM**: 高带宽内存、NAND闪存、企业SSD
- **AI云与数据中心**: 超大规模厂商资本支出、云AI服务
- **AI电力与散热**: 变压器短缺、液冷渗透率、数据中心能耗 — 当前最大瓶颈
- **AI PCB与先进封装**: 高多层PCB、CCL材料、CoWoS封装
- **AI网络/光通信**: 光模块（800G/1.6T）、CPO、AI交换机
- **AI应用**: 企业SaaS、自动驾驶、机器人、AI智能体
- **中美AI竞争**: 芯片出口管制、实体清单、开源vs闭源模型
- **AI监管**: 美国行政令、欧盟AI法案、中国AI治理规则
- **搜索关键词（中文）**: 人工智能, AI芯片, 大模型, 算力, 智算中心, 自动驾驶, 具身智能, 液冷, 变压器, 光模块, 先进封装, PCB, HBM

*具体公司、ticker、产业链图谱详见 `knowledge/ai-landscape.md` 和 `knowledge/watchlist-sectors.md`*

### Financial Markets & Trading
- **US Equities**: S&P 500 (^GSPC), NASDAQ (^IXIC), Dow Jones (^DJI)
- **China Equities**: Shanghai Composite (000001.SS), Hang Seng (^HSI), CSI 300 (000300.SS)
- **Commodities**: Gold (GC=F), Silver (SI=F), Oil WTI (CL=F), Brent (BZ=F), Copper (HG=F), NatGas (NG=F)
- **Currencies**: DXY (DX-Y.NYB), EUR/USD, USD/CNY, USD/JPY
- **Bonds**: US Treasury 2Y/10Y/30Y, Fed funds, China gov bond yields
- **Crypto**: BTC, ETH (if market-relevant)

## Available Tools

### Currently Connected
- **Exa** (`mcp__exa__web_search_exa`, `mcp__exa__web_fetch_exa`) — 语义搜索 + 内容抓取，支持中文
- **Yahoo Finance** (`mcp__yfinance__*`) — 股价、财报、新闻、期权
- **FRED** (`mcp__FRED_MCP_Server__*`) — 美国宏观（CPI/GDP/失业/NFP/利率/零售/通胀）
- **Alpha Vantage** (`mcp__alphavantage__*`) — 黄金/白银现货、技术指标(RSI/MACD/BBANDS)、外汇、新闻情感、商品
- **Playwright** (`mcp__playwright__*`) — 浏览器自动化（JS/付费墙/fallback）
- **天天基金网** (Playwright) — Chinese fund NAV: `https://h5.1234567.com.cn/app/fund-details/?fCode={基金代码}`

### Key Yahoo Finance Tickers
| Asset | Ticker |
|-------|--------|
| S&P 500 | `^GSPC` |
| NASDAQ | `^IXIC` |
| Dow Jones | `^DJI` |
| Shanghai Composite | `000001.SS` |
| Hang Seng | `^HSI` |
| Gold | `GC=F` |
| Silver | `SI=F` |
| Oil WTI | `CL=F` |
| Oil Brent | `BZ=F` |
| DXY | `DX-Y.NYB` |
| USD/CNY | `CNY=X` |
| US 10Y | `^TNX` |
| Copper | `HG=F` |

*AI/科技/供应链 ticker 详见 `knowledge/ai-landscape.md`；A 股细分板块详见 `knowledge/watchlist-sectors.md`*

### Tool Usage Quick Reference
| Tool | Use | Fallback |
|------|-----|----------|
| Yahoo Finance | 股价/财报/新闻 | `tool-fallback` skill → Playwright sina/eastmoney |
| FRED | 美国宏观 | → `fred.stlouisfed.org/series/{ID}` |
| Alpha Vantage | 技术指标/商品/情感 | → tradingview/tradingeconomics |
| Exa | 新闻搜索 | → 等 60-120s 重试，再 Playwright |
| Playwright | JS/付费墙/终极 fallback | (本身) |

工具失败 SOP 详见 `tool-fallback` skill 和 `knowledge/tool-fallbacks.md`。

### Price Data Rules
- **Always Yahoo Finance `get_stock_info`** for prices — 不用 Exa 搜索拿价格
- **A 股**：`.SS`(上交所) / `.SZ`(深交所)
- **基金/QDII**：天天基金网 via Playwright
- **黄金现货（人民币）**：Alpha Vantage 或 Exa 搜上海金交所

### Data Freshness Rules
- 用户时区 **UTC+8（北京时间）**。判断"今日"先用 `Bash date` 确认 BJT
- 市场时间（BJT）：A 股 9:30-11:30 + 13:00-15:00；港股 9:30-12:00 + 13:00-16:00；美股 21:30-04:00 (DST)
- Yahoo `marketState` 是权威：REGULAR/POSTPOST/PREPRE/PRE
- ⚠️ marketState=PREPRE 时 Yahoo 返回的"日内数据"实为上一交易日 stale 值
- 报告表格必标时间戳

## File Structure

```
daily-news/
├── CLAUDE.md                    # 项目说明 + skill 索引（本文件）
├── .claude/
│   └── skills/                  # 🎯 8 个可调用 skill（流程封装,单一 source of truth）
│       ├── daily-briefing/        # 主流程编排（17 步 + audit）
│       ├── signal-generation/     # ⭐ 信号 4 道闸 pipeline（技/Kelly/瓶颈/反方）
│       ├── bottleneck-analysis/   # 瓶颈资产框架（6问/三维度）
│       ├── fundamental-deepdive/  # 6 维度基本面 + G 框架
│       ├── data-validation/       # 数据验证 agent
│       ├── discover-new-stocks/   # 新标的发掘
│       ├── tool-fallback/         # 工具失败 SOP
│       └── briefing-audit/        # ⭐ 末尾自检（防软跳过）
├── knowledge/                   # Living knowledge base（数据,非流程）
│   ├── context.md               # 全球宏观/地缘/市场状态
│   ├── ai-landscape.md          # AI 产业图谱 + ticker
│   ├── watchlist-sectors.md     # 板块/子链/标的
│   ├── bottleneck-framework.md  # 瓶颈框架数据参考（AI 主线图/对标/持仓诊断）
│   ├── tool-fallbacks.md        # Fallback URL 速查 + Playwright 模板
│   └── prompt-evolution.md      # System prompt 改进日志
├── reports/                     # 每日简报 (中文) — YYYY-MM-DD.md
├── decisions/                   # Trading 决策记忆
│   ├── positions.md             # 当前持仓 & 关注清单（living）
│   ├── YYYY-MM-DD.md            # 每日决策日志
│   └── review.md                # 周期性回顾
├── research/                    # 课题研究
│   └── INDEX.md                 # 课题总索引
├── tools/                       # Python 工具
│   ├── technical.py             # MA/RSI/MACD/BB/ATR — `python tools/technical.py <file.json>`
│   ├── kelly.py                 # Kelly 仓位 — `python tools/kelly.py <price> <target> <stop> <winrate>`
│   └── save_prices.py           # 价格新鲜度检查 — `python tools/save_prices.py --check`
├── data/prices/                 # 历史价格 JSON（7 天过期）
└── sources.md                   # 跟踪源
```

## Knowledge Base System

**核心原则**：Knowledge docs 答"当前世界状态是什么？"；daily reports 答"今天发生了什么？"；CLAUDE.md 答"项目是什么 + 调用什么 skill？"；skills 答"如何分析？"。

### 各文件用途
- `knowledge/context.md` — 全球宏观/地缘/市场状态（每次报告后增量更新）
- `knowledge/ai-landscape.md` — AI 产业图谱 + ticker reference（重大 AI 进展时更新）
- `knowledge/watchlist-sectors.md` — 板块/子链/标的（新标的发现时更新）
- `knowledge/bottleneck-framework.md` — **数据参考**（AI 主线摊开图/海外对标表/误分类清单/持仓诊断）— 流程在 `bottleneck-analysis` skill
- `knowledge/tool-fallbacks.md` — **URL 速查表 + Playwright 提取模板** — 流程在 `tool-fallback` skill
- `knowledge/prompt-evolution.md` — System prompt 改进日志（用户要求更新 CLAUDE.md 时先读此文件批处理）

**核心规则**：knowledge/ = 数据，skills/ = 流程。同一信息只存一处，避免漂移。

### Knowledge Update Triggers

更新 `knowledge/context.md` 当：
- 央行变利率/转向（Fed/PBOC/ECB/BOJ）
- 新制裁/关税/贸易政策
- 地缘状态变（停火/升级/新冲突）
- 宏观数据大幅 surprise
- 市场 regime shift

更新 `knowledge/ai-landscape.md` 当：
- 重大模型发布或 benchmark 突破
- 新芯片出口管制或实体清单变化
- 公司估值因 AI 新闻 >10% 变动
- 新 AI 监管出台
- 供应链中断（fab/芯片短缺）
- **新供应链瓶颈出现**
- 供应链定价权变化（涨价/降价周期）

更新 `knowledge/watchlist-sectors.md` 当：
- 新板块/子板块识别
- 现有板块发现新公司
- 产业链下钻发现被忽视细分
- 产业集群模式出现
- 板块逻辑被证伪/确认

## Memory & Decision Tracking System

### 1. Daily Decision Log (`decisions/YYYY-MM-DD.md`)

```markdown
# 决策日志 — YYYY-MM-DD

## 今日发出的信号
### 短期（1-3个月）
| # | 操作 | 标的 | 入场价格 | 逻辑 | 反方观点 | 目标/止损 | 赔率 | Kelly仓位 | 信心 | 状态 |
|---|------|------|----------|------|----------|-----------|------|-----------|------|------|

### 中期（3-6个月）/ 长期（6-12个月+）
（同上结构）

## 此前信号跟进
| 原始日期 | # | 标的 | 原始操作 | 当前价格 | 盈亏 | 更新 | 新状态 |

## 数据警示（fallback 记录）
- [数据点] — [失败工具] → [fallback 来源]

## 明日关注要点
```

### 2. Positions Tracker (`decisions/positions.md`)

Living document — 单一事实源：

```markdown
# 活跃持仓与关注清单

## 开仓持仓（短期/中期/长期分表）
| 开仓日期 | 标的 | 操作 | 入场价 | 当前价 | 盈亏 | 止损 | 止盈 | 状态 | 备注 |

## 关注清单（等待入场）
| 添加日期 | 标的 | 计划操作 | 触发条件 | 备注 |

## 近期平仓
| 开仓 | 平仓 | 标的 | 操作 | 入场 | 出场 | 盈亏 | 原因 |
```

### 3. Periodic Review (`decisions/review.md`)
- 准确率追踪
- 经验教训
- 偏差检查

## Report Format

`reports/YYYY-MM-DD.md` 结构：

```markdown
# 每日情报简报 — YYYY-MM-DD

## 与昨日相比的变化
- 隔夜/上次报告以来的主要变动
- 持仓更新（止损/止盈是否触发）
- 此前信号跟进

## 美股市场概览（前一交易日收盘）
| 资产 | 价格 | 涨跌 | 趋势 |

## 中国市场概览（当日收盘）
| 资产 | 价格 | 涨跌 | 趋势 |

## 大宗商品（最新）
| 资产 | 价格 | 涨跌 | 趋势 |

## 美国新闻与经济
## 中国新闻与经济
## 中美关系与贸易
## 全球地缘政治

## AI与科技
- AI 模型/芯片/资本支出
- 中美 AI 竞争
- AI 相关股票（附代码+价格）
- **AI 供应链瓶颈追踪**（电力/液冷/HBM/PCB/封装）
- 供应链涨跌幅对比 + 滞后板块标注

## 课题进展跟踪
- research/INDEX.md 中活跃课题的当日进展

## 关键风险与关注清单

## 操作建议 — 中国股票持仓信号

**投资风格：中长期持仓，非短线交易。** 最短 1 个月。

### 短期（1-3 月）/ 中期（3-6 月）/ 长期（6-12 月+）
| 操作 | 标的 | 入场逻辑 | 目标/止损 | 赔率 | Kelly 仓位 | 信心 | 催化剂/退出条件 |

### 信号生成 / 仓位 / 卖出标准

**所有信号必须通过 `signal-generation` skill 4 道闸**：技术面 + Kelly 仓位 + 瓶颈硬约束 + Devil's Advocate。详细规则在 skill 文件中,CLAUDE.md 不再重复。

### 重要声明
以上信号仅供信息参考和教育用途，不构成投资建议。
```

## Guidelines

- Cite sources with URLs
- Distinguish facts from analysis
- Note data timestamps — markets move fast
- Flag low-confidence/unverified info
- Keep reports concise — focus on what matters for trading decisions
