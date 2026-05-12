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
