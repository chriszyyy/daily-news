# 工具 Fallback — URL 速查表

*流程/SOP 已迁移到 `.claude/skills/tool-fallback/`,本文件仅保留 URL 映射 + Playwright 提取代码模板。*

*最后更新:2026-05-10*

## 各 MCP 的 Fallback URL 映射

### Exa 搜索失败 → 网站

| 数据需求 | Backup URL |
|----------|-----------|
| 美股财经新闻 | finance.yahoo.com/news, cnbc.com, reuters.com/markets |
| 中文财经 | finance.sina.com.cn, eastmoney.com, 21jingji.com, cls.cn |
| 中美关系 | scmp.com, voachinese.com, weforum.org |
| AI/科技 | techcrunch.com, theverge.com, ofweek.com |
| Fed/官方 | federalreserve.gov/newsevents/speeches.htm |
| 中国官方 | customs.gov.cn, stats.gov.cn, pbc.gov.cn |

### Yahoo Finance 失败 → 网站

| 数据需求 | Backup URL |
|----------|-----------|
| 美股价格 | finance.yahoo.com/quote/{TICKER} / stockanalysis.com/stocks/{ticker}/ |
| A股价格(上交所6/5开头) | finance.sina.com.cn/realstock/company/sh{code}/nc.shtml |
| A股价格(深交所0/3开头) | finance.sina.com.cn/realstock/company/sz{code}/nc.shtml |
| A股备份 | quote.eastmoney.com/{code}.html |
| 港股 | finance.yahoo.com/quote/{TICKER}.HK / aastocks.com/sc/stocks/quote/detail-quote.aspx?symbol={code} |
| 中概股 | nasdaq.com/market-activity/stocks/{ticker} |
| 财报 | stockanalysis.com/stocks/{ticker}/financials/ |
| 财报(中文) | data.eastmoney.com/zycwzb/{代码}.html |
| 商品 | finance.yahoo.com/commodities / tradingeconomics.com/commodity/{name} |

### FRED 失败 → 网站

| 数据需求 | Backup URL |
|----------|-----------|
| 任意系列 | fred.stlouisfed.org/series/{ID} |
| 通用宏观 | tradingeconomics.com/united-states/indicators |
| 10Y/30Y 收益率 | cnbc.com/quotes/US10Y / finance.yahoo.com/quote/^TNX |
| 利率期货预期 | cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html |
| Fed 日历 | federalreserve.gov/monetarypolicy/fomccalendars.htm |
| BLS NFP | bls.gov/news.release/empsit.htm |
| BEA GDP/PCE | bea.gov/news |

### Alpha Vantage 失败 → 网站

| 数据需求 | Backup URL |
|----------|-----------|
| 黄金现货(国际) | gold.org/goldhub/data/gold-prices |
| 黄金(中文) | quote.eastmoney.com/qihuo/AU0.html |
| 上海金 | sge.com.cn |
| RSI/MACD(美股) | tradingview.com/symbols/{TICKER}/technicals/ |
| 技术指标(A 股) | xueqiu.com/S/{代码}/technicals |
| 新闻情感 | finviz.com/quote.ashx?t={ticker} |
| 自己计算 | `python tools/technical.py <price_file.json>` |

### 天天基金网(QDII/基金 NAV)

- 主:`https://h5.1234567.com.cn/app/fund-details/?fCode={基金代码}`
- 备 1:`http://fund.eastmoney.com/{代码}.html`
- 备 2:`https://www.howbuy.com/fund/{代码}/`

## 全球指数/商品速查

| 资产 | URL |
|------|-----|
| S&P 500 | finance.yahoo.com/quote/%5EGSPC |
| NASDAQ | finance.yahoo.com/quote/%5EIXIC |
| 上证 | finance.sina.com.cn/realstock/company/sh000001/nc.shtml |
| 恒生 | finance.yahoo.com/quote/%5EHSI |
| 黄金 | tradingeconomics.com/commodity/gold |
| 原油 WTI | tradingeconomics.com/commodity/crude-oil |
| DXY | tradingeconomics.com/united-states/currency |

## Playwright 通用提取代码模板

### A 股个股(sina)

```javascript
() => {
  const price = document.querySelector('#price')?.innerText;
  const change = document.querySelector('#change')?.innerText;
  const pct = document.querySelector('#changePercent')?.innerText;
  return { price, change, pct };
}
```

### 通用 fallback 提取

```javascript
() => document.body.innerText.substring(0, 5000)
// 然后用文本/regex 解析
```

### 等待页面加载

```javascript
() => document.readyState === 'complete'
```

## 反爬虫备用镜像

| 主站 | 备用 |
|------|------|
| sina.com.cn | finance.sina.cn |
| eastmoney.com | quote.eastmoney.com |
| yahoo.com | finance.yahoo.co.jp(日版) |

## Exa 通用搜索流程(Playwright 模拟)

```
1. browser_navigate → 目标网站搜索页
2. browser_snapshot → 获取页面结构
3. browser_type → 在搜索框输入关键词
4. browser_press_key Enter
5. browser_evaluate → 提取结果文本
6. 解析后写入报告
```
