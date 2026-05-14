---
name: price-trigger-watch
description: 扫描 positions.md 关注清单的"触发条件"列,判断当日是否命中。命中才进 signal-generation 走完整 4 道闸,未命中当日不深度研究,节省 token + 避免对同一池子无效空跑。daily-briefing P3.0 必调。
---

# Price Trigger Watch

**轻量扫描器**——把价格触发器变成一等公民。Daily-briefing 不再每天对 watchlist 全量做深度研究,只对**今日触发**的标的进 signal-generation。

## Contract

- **Triggers**: daily-briefing P3.0 (P3.1 瓶颈扫描之前) / 用户问"今天哪些触发器命中了"
- **Inputs**: `decisions/positions.md` 关注清单 + 当日实测价(BJT)
- **Outputs**: 命中清单(0-N 个标的)→ 传给 signal-generation 走完整 5 Gate;未命中清单(供报告附录)
- **Calls**: `tool-fallback`(数据失败时)
- **Called by**: `daily-briefing`(P3.0 强制)、用户

## ⚠️ 强制规则

1. **只读 positions.md**,不读 knowledge/ 价格(SSOT)
2. **触发判定必基于当日实测价** — 跨午休/收盘必重拉
3. **触发命中 → 必走 signal-generation 完整流程** — 不能跳 Gate
4. **未触发 → 不做深度研究** — 避免对未触发标的浪费 token
5. **数据失败立即调 tool-fallback** — 不能"假设没触发"

## 流程(3 步)

### Step 1: 解析触发条件

读 `decisions/positions.md` 中"关注清单"段所有"触发条件"列,解析为结构化判定:

| 触发类型 | 示例条件 | 判定逻辑 |
|---|---|---|
| **价格区间** | "¥23.40-23.80 入场" | 当日价 ∈ [23.40, 23.80] = 命中 |
| **价格跌破** | "跌至 ¥17.5 以下" | 当日价 < 17.5 = 命中 |
| **价格突破** | "突破 MA20 ¥24.7" | 当日价 > 24.7(且需查 MA20 现值)= 命中 |
| **价格 + 技术面复合** | "回踩 MA20 + 改色阳线" | 价格区间 OK **且** 技术面命中 = 命中 |
| **业绩触发** | "Q1 扭亏为盈" | 业绩公告日检查 |
| **政策触发** | "Trump 议程明朗" | 事件日人工判定 |
| **失效条件** | "跌破 ¥23.40 = 信号作废" | 当日价 < 23.40 = 该触发器删除 |

### Step 2: 拉当日实测价 + 校验

对每个触发器标的:
1. Yahoo `get_stock_info` 拿实测价 + `regularMarketTime`
2. **stale 守卫**:`regularMarketTime` 转 BJT 落后 >15min / 跨午休未刷 → 立即 Playwright 东财
3. 复合触发还需:`get_historical_stock_prices period=1mo` + `python tools/technical.py` 拿 MA20/RSI/MACD

### Step 3: 输出三类清单

#### 3.1 ✅ 命中清单(必走 signal-generation)
```
| 标的 | 代码 | 触发条件 | 当日价 | 命中类型 |
|---|---|---|---|---|
```
**每个命中 → 立即调 `signal-generation` skill 走完整 5 Gate(Gate 1+2+2.5+3+4)**。

#### 3.2 ⚠️ 失效清单(从关注清单删除)
```
| 标的 | 代码 | 失效条件 | 当日价 | 处理 |
|---|---|---|---|---|
```
**写入决策日志"今日触发器失效"段,positions.md 关注清单删除该行**。

#### 3.3 ⏸ 未触发清单(报告附录,不深度研究)
```
| 标的 | 当日价 | 触发距离 | 备注 |
|---|---|---|---|
```
**只列名 + 距触发的 % 距离,不再下钻**。

## 输出格式(写入 daily-briefing 报告 + 决策日志)

### 报告中(reports/YYYY-MM-DD.md)
```markdown
## 价格触发器扫描(今日)

**命中**: N 个 → 走 signal-generation
**失效**: M 个 → 从 watchlist 删除
**未触发**: K 个(详见附录)

[3.1 / 3.2 / 3.3 三表]
```

### 决策日志中(decisions/YYYY-MM-DD.md)
```markdown
## 今日触发器扫描

### 命中(已进 signal-generation)
- [标的] 当日价 ¥X 触发"[条件]" → 4-Gate 输出见下文

### 失效(已从 watchlist 删除)
- [标的] 当日价 ¥X 触发失效条件"[条件]"

### 未触发(K 个,不深度研究)
- 列表略,详见 positions.md
```

## 与其他 skill 的关系

```
daily-briefing P3.0
    │
    ▼
price-trigger-watch (本)
    │
    ├─→ 命中 → signal-generation (Gate 1-4 完整)
    │              │
    │              └─→ Gate 2.5 可交易性 OK → 入决策日志
    │
    ├─→ 失效 → 直接 Edit positions.md 删除
    │
    └─→ 未触发 → 报告附录,跳过 P3.1-P3.3 深度研究

daily-briefing P3.1 (瓶颈扫描) 仅对"持仓 + 命中触发器"做,不再对全 watchlist
```

## Why(为什么需要这个 skill)

**2026-05-08 至 5/14 教训**:每天对 watchlist 30+ 标的做"瓶颈扫描 + 6 维深度",90% 标的根本没到买点。结果:
- 5/14 deepdive 三个候选(大秦/盛和/复星)花 60 分钟,**0 命中** — 其中盛和/复星属于"价格在区间外不该研究"
- watchlist 触发器(沃尔核材"突破 MA20 ¥24.7"、华天科技"回调至 ¥12.5-13")长期没被定期检查,**机会可能被错过**

**有了 price-trigger-watch**:
- 每天 5-10 分钟扫完整个 watchlist,清单化展示
- 命中才进深度研究 — 信噪比从 ~10% 升到 ~80%
- 失效自动清理 — watchlist 不会越积越脏

## 反模式(严禁)

- ❌ "我感觉今天 XX 应该到位了" — 必须实测价
- ❌ 触发命中后只写"建议入场" — 必走 signal-generation 拿 4-Gate 输出
- ❌ 失效条件命中但不删 watchlist — 下次还会被扫,浪费
- ❌ 未触发也做 6 维深度研究 — 违反本 skill 设计目的
