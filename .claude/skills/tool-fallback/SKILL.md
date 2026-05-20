---
name: tool-fallback
description: 工具失败时的 fallback SOP——永远不让工具问题终止任务。任何 MCP 工具(Exa/Yahoo/FRED/AlphaVantage)失败、限流、超时、返回空数据时使用。提供 Playwright 直接浏览源网站的备用路径。绝不跳过数据点。
---

# 工具失败 Fallback SOP

**本 skill 是 fallback 流程的唯一来源**。`knowledge/tool-fallbacks.md` 仅保留 URL 速查表和 Playwright 提取代码模板。

## Contract

- **Triggers**: 任何 MCP 工具失败/限流/超时/返回空数据/数据明显过时
- **Inputs**: 失败的工具名 + 想获取的数据类型(价格/新闻/财报/宏观)
- **Outputs**: 用 fallback 路径取得的数据 + 来源标注("via Playwright fallback @ source")
- **Calls**: 无
- **Called by**: 所有数据相关 skill(daily-briefing 各 phase, signal-generation, fundamental-deepdive, data-validation 等)

## 🔴 核心原则

**永远不让工具问题终止任务**。每个 MCP 都有 Playwright fallback。

## 优先级金字塔

```
Level 1: MCP 工具(最快)
   ↓ 限流/失败
Level 2: WebFetch(已知 URL)
   ↓ 失败
Level 3: Playwright(浏览器自动化)
   ↓ 极端
Level 4: 标 ⚠️ 数据缺失 + 历史/缓存 + 报告警示
```

## SOP

```
任意工具调用失败:
├── 第 1 次: 等 60s 重试 (Bash sleep 60)
├── 第 2 次: 等 120s 重试
├── 第 3 次: 触发 fallback
│   ├── 查 knowledge/tool-fallbacks.md URL 表
│   ├── Playwright browser_navigate
│   ├── 提取数据
│   └── 标 "via Playwright fallback @ source"
└── 仍失败:
    ├── decisions/YYYY-MM-DD.md 写"数据警示"
    ├── 用最近一次缓存
    ├── 报告中明确 ⚠️
    └── 任务继续,绝不中止
```

## 何时立即 fallback

| 信号 | 立即 fallback |
|------|--------------|
| 返回 "rate limit" | ✅ |
| HTTP 503/429 | ✅ |
| 连续 3 次 timeout | ✅ |
| 返回空数据但应该有 | ✅ |
| 数据明显过时(>3 天) | ✅ |
| **Yahoo `regularMarketTime` 转 BJT 落后当前 >15 分钟 且 marketState=REGULAR** | ✅ **直接 Playwright,不重试** |
| **BJT >15:15 但 Yahoo 仍返回 marketState=REGULAR** | ✅ **直接 Playwright** |
| **跨午休/开盘/收盘分界后 Yahoo 数据未更新** | ✅ **直接 Playwright** |
| **Volume 异常低于历史均值**(只截到半天数据) | ✅ |
| **用户明说"开盘了"/"收盘了"但 Yahoo 数据时点对不上** | ✅ **直接 Playwright,不要"warning 后继续"** |

## 🎭 Stale 数据 → Playwright 实测 SOP

**这是 stale-data 处理的唯一权威路径**。CLAUDE.md / 其他 skill 检测到 stale → 调本 skill。

### 步骤
1. **`Bash date`** 拿当前 BJT,计算 Yahoo `regularMarketTime` 与当前时差
2. 时差 >15min 且 marketState=REGULAR → 进入 Playwright fallback
3. **A 股**:`browser_navigate` → `https://quote.eastmoney.com/sh{code}.html`(沪)/`sz{code}.html`(深)
4. **港股**:`https://quote.eastmoney.com/hk/{5位代码}.html`
5. **美股**:`https://quote.eastmoney.com/us/{TICKER}.html`
6. **抓 `<title>` 直接拿"最新价 涨跌(涨幅%)"** — 东财把核心信息塞进 title,最快路径
7. `browser_evaluate` 抓 `<table>` DOM 获取五档 / 高低 / 量比 / PE
8. 标注"东方财富 BJT XX:XX 实测"
9. **🔴 立即 `mcp__playwright__browser_close`** — 不留残留 tab
10. 输出数据给调用方

### 东方财富快速提取模板

```javascript
// 抓五档/高低/量比 — 适用 quote.eastmoney.com 个股页
() => {
  const data = {};
  document.querySelectorAll('table').forEach(t => {
    const txt = t.innerText.trim();
    if (txt.includes('卖') || txt.includes('买') || txt.includes('最高') || txt.includes('成交')) {
      data['table_' + Object.keys(data).length] = txt.substring(0, 600);
    }
  });
  return { title: document.title, ...data };
}
```

### 🔴 用完必关闭浏览器(资源管理)
- 每次 Playwright 任务结束 → **必须** `mcp__playwright__browser_close`
- 一对话最多 1 个 tab 活跃,串行用完关下一个再开
- 反模式:
  - ❌ 拉完继续聊别的不关 — 残留 Chrome 进程占内存
  - ❌ 同时开 5 个 tab 拉 5 只股 — **必须串行 + close**
  - ❌ "用户可能还要看"留着 — 不要预判
- 用户 2026-05-13 明确要求:"用完记得关闭 playwright chrome 窗口"

## 何时不要 fallback

| 情况 | 处理 |
|------|------|
| "无数据"但市场逻辑确实没有 | 接受 |
| API key 失效(非限流) | 通知用户,不要硬试 |
| 网站本身 down | 跳到下一个 backup |

## URL 速查 / Playwright 模板

详见 `knowledge/tool-fallbacks.md`(纯参考数据,持续更新)。
关键映射快速记忆:
- Exa 限流 → cnbc.com / reuters.com / sina.com.cn / eastmoney.com
- Yahoo A 股失败 → finance.sina.com.cn/realstock/company/sh{code}/nc.shtml
- Yahoo 美股失败 → stockanalysis.com/stocks/{ticker}/
- FRED 失败 → fred.stlouisfed.org/series/{ID}
- 黄金现货失败 → quote.eastmoney.com/qihuo/AU0.html

## Playwright 通用故障

### 加载慢/超时
```
browser_wait_for time=5
browser_snapshot
```

### 反爬虫(403/验证码)
- sina.com.cn → finance.sina.cn
- eastmoney.com → quote.eastmoney.com

### JS 未渲染
```
browser_wait_for time=3
browser_evaluate `() => document.readyState === 'complete'`
```

### 元素定位失败
直接:
```
browser_evaluate `() => document.body.innerText`
```
然后用文本/regex 提取。

## 记录到决策日志

每次 fallback 写入当日 `decisions/YYYY-MM-DD.md` 的"数据警示"区,方便复盘和优化。

---

## 🤖 子代理(subagent)调用 SOP — 必读

### 核心问题

**子代理不继承**:
- ❌ `.claude/skills/` 任何 skill(包括本 skill)
- ❌ CLAUDE.md
- ❌ memory/MEMORY.md(包括 feedback_exa_rate_limit / feedback_tool_fallback_required)
- ❌ tool-fallback SOP / 重试机制 / Playwright 兜底意识

**只部分继承**:
- ⚠️ MCP 工具 — 看子代理类型;`general-purpose` 理论上有但**实际经常缺**(典型:yfinance 不可用 → 自己摸索 fallback 但不 SOP 化)

**典型表现**(用户 2026-05-18 观察):
- Exa 限流 → 子代理"接受缺失,标⚠为估算",不重试不 Playwright
- yfinance 缺 → 子代理凭直觉用东财 push2,但不会按 SOP 用 Playwright
- 任何失败 → 直接降级返回部分数据,**不通知主 session**

### 🔴 主 Claude 启动子代理的 3 条铁律

1. **prompt 头部必注入 SOP 摘要**(2-3 句,不要全文)
2. **关键数据(价格/业绩/事实)优先主 session 实测**,子代理只做汇总/分析
3. **子代理返回如有 ⚠估算/未实测/限流字样 → 主 session 立即补测**,不能直接采用

### SOP 摘要模板(粘贴到 prompt 头部)

```
**工具失败 SOP**(必遵守):
- 任何 MCP 工具失败/限流/超时 → 等 60s 重试 1 次 → 仍失败 immediately Playwright fallback
- Exa 限流 → Playwright navigate 到中文源(quote.eastmoney.com / finance.sina.com.cn / cninfo.com.cn)
- Yahoo 不可用 → 东财 push2 API 或 Playwright quote.eastmoney.com
- Playwright 用完必 browser_close,一对话最多 1 个 tab
- 任何数据点不允许标"⚠估算"或"未实测"跳过 — 必须用 fallback 取真值
- stale 数据(regularMarketTime >15min 落后)同样必 Playwright,不接受
```

### 反模式(主 session 严禁)

- ❌ 启动子代理只说"用 mcp__exa__web_search_exa 查 XX",不说限流怎么办
- ❌ 启动子代理委托查实时价格 — 价格是事实查询,主 session 自己拉
- ❌ 子代理返回 "⚠估算" 直接写入决策日志 — 必须补测后再写
- ❌ 看到 "Skipping TaskCreate" / "数据未实测" 就忽略,假装没看见

### 子代理类型选择

| 类型 | 何时用 |
|---|---|
| `Explore` | 纯代码搜索(grep / glob / read),只读 |
| `general-purpose` | 多步研究 + 工具组合,但**必须注入 SOP** |
| `Plan` | 设计方案,不执行 |

数据查询 + 信号 pipeline → 优先 `general-purpose` + **强制 SOP 注入**。
