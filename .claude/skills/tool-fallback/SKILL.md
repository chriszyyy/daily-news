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
