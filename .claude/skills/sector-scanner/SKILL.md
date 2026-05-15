---
name: sector-scanner
description: 全 A 股系统化二三线扫描器(备用,已停用 cron)。仅在用户明确说"我感觉 discover 漏了什么"/"系统扫一下全市场"时使用。日常发掘新标的优先用 discover-new-stocks。Python 客观规则筛选 5500+ 只 → AI 链命中 + 4 维评分 → Top 10 解读。
---

# Sector Scanner — 全 A 股系统化扫描(⚠️ 备用)

## 状态:备用,非默认流程

**2026-05-15 决策**:scanner 已搭建完成但**默认不启用**,cron 已取消。原因:
1. `discover-new-stocks` 已覆盖 80% 的"找新标的"价值
2. 用户资金 ¥55K + 主线持仓 5-8 只,不需要 50 只候选 CSV
3. A 股权限缺创业板/科创板/北交所,实际可选池 <2000 只
4. L1 抓取易被 ban IP,维护成本高

**何时重启**:用户明确说"我感觉 discover 漏了什么"/"系统扫一下全市场"/"我想看看全 A 股冷门标的"时手动调用。

## Contract

- **Triggers**:
  - 用户主动:"扫描一下全市场" / "做个系统扫描" / "找漏网之鱼" / "周度复盘"
  - 自动:cron 周日 21:07 BJT
  - 升级调用:`discover-new-stocks` 不足 5 只时降级到 scanner
- **Inputs**: `--chain pcb_hbm|cooling|power|optical|all`(默认 all)
- **Outputs**:
  - `data/scanner/raw-YYYY-MM-DD.json`(L1 全市场快照)
  - `tools/scanner/output/YYYY-MM-DD-scan.csv`(L2 排序候选)
  - `reports/scan-YYYY-MM-DD.md`(L3 Top 10 解读)
- **Calls**: `Bash`(L1+L2 Python)、`Yahoo MCP`(Top 20 精验)、`Exa`(随机 5 只业务验证)、`tool-fallback`(失败时)
- **Called by**: 用户 / cron / `discover-new-stocks`(扩展模式)

## 设计哲学

**为什么需要 sector-scanner**:`discover-new-stocks` 用 Exa 语义搜索找特定板块的新标的,但池子来自训练数据 + 已知行业图谱,**不是穷举扫描**。冷门优质二三线可能因为我没听过而漏掉。Scanner 用 Python 客观规则覆盖全 A 股 5500+ 只,消除候选池盲点。

**与 discover-new-stocks 的分工**:

| sector-scanner | discover-new-stocks |
|---|---|
| **主动**:周度全市场扫描 | **被动**:信号股过热时找替代 |
| **客观**:Python 评分硬规则 | **语义**:Claude + Exa 搜索 |
| **广**:全 A 股 5500+ | **深**:特定板块 5-10 只 |
| 输出 CSV + 解读 | 输出 watchlist 增量 |

scanner 是 discover 的"全集探针",discover 是 scanner 的"深度跟进"。
扫描发现的 Top 候选可投喂给 discover 做精研。

## 5 步流程

### Step 1:运行 L1 抓取(30 秒~10 分钟)

```bash
python tools/scanner/fetch_eastmoney.py
```

**预期**:`data/scanner/raw-YYYY-MM-DD.json` 生成,total_count ≥ 5000。

**校验**:
```bash
python -c "import json,sys,io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8'); d=json.load(open('data/scanner/raw-YYYY-MM-DD.json',encoding='utf-8')); print('count:', len(d['stocks']), 'fetched:', d['metadata']['fetched_at'])"
```

**失败处理**:
- AkShare 限流(RemoteDisconnected) → 等 30 分钟重试,或 fallback 直接东财 push2 API(`tools/scanner/fetch_eastmoney.py` 内已封装)
- 持续失败 → 用昨日 raw JSON,在报告顶部标 `data_source: stale-1d`

### Step 2:运行 L2 评分(秒级)

```bash
python tools/scanner/score.py --input data/scanner/raw-YYYY-MM-DD.json --top 50
```

**默认输出**:`tools/scanner/output/YYYY-MM-DD-scan.csv`(Top 50 全维度打分)

**校验**:Top 10 控制台预览必看 — 检查:
- 创业板 (300/301) / 科创板 (688) / 北交所 (4/8/9) 全被排除
- 价格 ≤¥40 / 市值 ¥30-300亿 / 非次新
- AI 链命中 (chain 字段非空)

### Step 3:Top 20 Yahoo MCP 精验

对 CSV Top 20 调用 `mcp__yfinance__get_stock_info`,补充 L1 缺的字段:
- `forwardPE` / `earningsQuarterlyGrowth` / `returnOnEquity`
- `regularMarketPrice` 与 CSV 价交叉验证(差 >2% 标 `[价差警告]`)

**注**:A 股代码必加后缀 `.SS`(6/9 开头) 或 `.SZ`(0/3 开头)。

**Yahoo 限流处理**:跳过失败的,在报告"数据警示"段记录"Top 20 中 N 只 Yahoo 不可用"。

### Step 4:Exa 业务真实性抽查(随机 5 只 Top 30)

随机选 5 只(避免每周看同样的),对每只搜索:
```
{公司名} AI 服务器 OR 液冷 OR 光模块 OR 变压器 客户 订单 2026
```

**评分调整**:
- 命中明确客户/订单(英伟达/华为/三大运营商等)→ `match_strength` 升级"strong",备注"业务验证"
- 命中纯题材/无落地 → 总分 -10,备注"题材股警示"
- Exa rate-limit → 跳过该只,不阻塞流程

### Step 5:生成报告 `reports/scan-YYYY-MM-DD.md`

```markdown
# 全 A 股 AI 链扫描报告 YYYY-MM-DD

**扫描时间**: HH:MM BJT
**数据源**: AkShare stock_zh_a_spot_em
**全 A 股总数 / 通过硬约束 / AI 链命中**: NNNN / NNN / NN

## 硬约束总览
- 价格 ≤¥40 / 市值 ¥30-300亿 / 52w 涨幅 <+150% (光模块 <+200%)
- 排除:创业板 (300/301)、科创板 (688)、北交所 (4/8)、ST、上市<60天
- 已排除创业板 NN 只 / 科创板 NN 只 / 价格超阈 NN 只 / 市值超阈 NN 只

## 4 链 Top 5

### A. PCB / HBM / 先进封装
| rank | code | name | price | mc(亿) | PE | score | 备注 |
| ... |

### B. 液冷 / 散热
...

### C. 变压器 / 电源 / 配电
...

### D. 光模块 / 光器件
...

## 跨链综合 Top 10
| rank | chain | code | name | price | mc | PE | score | 一句话 |
| ... |

## 建议加入 watchlist 的 3-5 只
- code 名 — 入选理由(估值/业绩/AI 关联/技术形态四维)

## 数据警示
- L1: ...
- L2: ...
- L3 Yahoo: 失败 N 只
- L3 Exa: 限流 N 只
```

## 默认评分权重(固化在 `tools/scanner/score.py`)

| 维度 | 权重 | 说明 |
|---|---|---|
| **估值** | 30 | PE<20:20分 / 20-30:15 / 30-50:8 / >50:0;PB<3:10 / 3-5:6 / 5-8:3 / >8:0 |
| **业绩(代理)** | 30 | 60d 涨幅适度 + 换手率 1-5% 健康。L3 用真实 Q1/forwardPE 精算 |
| **技术(代理)** | 20 | YTD 涨幅在 0-30% 健康区间 + 今日尾盘强度 |
| **AI 关联** | 20 | 公司名命中关键词 strong (20分) / 行业命中 weak (10分) / 无 (0) |

**修改权重**:直接编辑 `tools/scanner/score.py` 顶部的 `HARD_FILTERS` + 各 `score_*` 函数。
**新增关键词**:编辑 `tools/scanner/ai_keywords.py` 的 `AI_CHAIN_KEYWORDS` / `INDUSTRY_HINTS`。

## 数据警示约定

| 情况 | 处理 |
|---|---|
| L1 抓取失败/不足 5000 | 标 `data_source: stale-Nd` 用昨日数据,顶部明示 |
| L2 PE/Q1 缺失 | 用 N/A 而非 0(避免错误打分) |
| 创业板/科创板硬过滤 | 报告顶部明示"已排除 NN 只(权限)" |
| Yahoo 限流 | Top 20 中跳过失败的,记录到"数据警示" |
| Exa rate-limit | 抽样 5 只跳过失败,不阻塞 |
| CSV/data 落盘膨胀 | 仅保留最近 30 天,Step 5 末尾清理(见下) |

## 月度清理(Step 5 末尾自动)

```bash
# 删除 30 天前的 raw JSON 和 scan CSV
find data/scanner -name "raw-*.json" -mtime +30 -delete
find tools/scanner/output -name "*-scan.csv" -mtime +30 -delete
```

Windows 环境:
```bash
forfiles /p "data/scanner" /m "raw-*.json" /d -30 /c "cmd /c del @path"
```

## cron 续期(每 7 天)

cron 周日 21:07 任务 7 天后会过期。每次 review 时检查:
```
CronList → 看 sector-scanner 的 next_run,过期则 CronCreate 续期
```

## 与 daily-briefing 的衔接

- daily-briefing P3.0(price-trigger-watch)只看 watchlist 触发器
- sector-scanner 是 watchlist 之外的"全集探针"
- 每周日 cron 自动跑后,周一 daily-briefing 顶部应引用 `reports/scan-YYYY-MM-DD.md` 的 Top 候选

## 不做什么

- ❌ 不直接污染 watchlist:用户决定哪些 Top 候选进 watchlist
- ❌ 不做最终决策:CSV/报告是排序入口,真买卖必走 signal-generation 5 道闸
- ❌ 不替代 discover-new-stocks:scanner 是广度扫描,discover 是深度搜索

## 参考

- 实现计划:`.claude/plans/calm-doodling-teacup.md`
- L1 代码:`tools/scanner/fetch_eastmoney.py`
- L2 代码:`tools/scanner/score.py`
- 关键词:`tools/scanner/ai_keywords.py`
