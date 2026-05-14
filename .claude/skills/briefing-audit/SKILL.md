---
name: briefing-audit
description: daily-briefing 末尾的强制自检 meta-skill。检查 17 步是否全跑、4 道闸是否全过、每个信号是否走了 signal-generation、knowledge 更新是否被遗漏、fallback 是否记录。Audit 报告写入决策日志末尾。漏调用必标红。
---

# Briefing Audit

**daily-briefing 的强制最后一步**。防止 skill 被"软跳过"——今天 briefing 执行未显式调用 kelly-position-sizing 等 skill 而无人发现,就是这个 skill 要解决的问题。

## Contract

- **Triggers**: daily-briefing 最后一步(P3.x final);用户说"audit 一下今天的 briefing"
- **Inputs**: 当日 TodoWrite 状态 + reports/YYYY-MM-DD.md + decisions/YYYY-MM-DD.md
- **Outputs**: Audit 报告 markdown,append 到 `decisions/YYYY-MM-DD.md` 末尾
- **Calls**: 无(纯检查,不调用其他 skill)
- **Called by**: `daily-briefing`(强制最后一步)

## 5 类自检

### Check 1: 17 步是否全跑

读 TodoWrite 当前状态:

- 所有 status 必须为 `completed`
- 任何 `pending` / `in_progress` → 🔴 **FAIL**
- 输出未完成步骤列表

### Check 2: 信号 Pipeline 是否全过(每条新信号 / 加减仓)

读 `decisions/YYYY-MM-DD.md` "今日发出的信号" + "今日触发器扫描" + "持仓加减仓" 三段,**先判定 pipeline 类型**:

| 信号类型 | 应走 pipeline | 必跑 Gate |
|---|---|---|
| 新建仓(标的不在 positions.md 持仓段) | `signal-generation` | Gate 1 + 2 + 2.5 + 3 + 4 |
| 加仓 / 减仓 / 止盈 / 止损(标的已在 positions.md) | `signal-rebalance` | Gate 1 + 2.5 + 4(止损止盈跳 Gate 1)|

**Router 误路由检测**:
- 标的在 positions.md 但走了 signal-generation 5 Gate → ⚠️(浪费但不算错)
- 标的不在 positions.md 但走了 signal-rebalance 3 Gate → 🔴 **FAIL**(缺 Kelly + 瓶颈)

**新建仓信号检查**:

| Gate | 检查项 | 失败标准 |
|------|--------|---------|
| Gate 1 技术面 | 信号行有"赔率"列且非空 | 缺失 → ⚠️ |
| Gate 1 **4 维位置** | 信号有 52w+区间分位/近20日/近5日/放量 4 数 | 缺失 → 🔴 **FAIL** |
| Gate 1 **滞涨标签校验** | 若信号叙事含"滞涨/认知差/未被定价",4 维任一阈值命中(近5日>10% / 近20日>15% / 距52w高<15% / 放量) → 标签必须取消 | 未取消 → 🔴 **FAIL**(国茂 5/12 教训) |
| Gate 2 Kelly | 信号行有"Kelly仓位"列且非空 | 缺失 → ⚠️ |
| Gate 2.5 **可交易性** | 信号行有"100/200 股价值 + 净赔率 b' + 现金校验" 3 项 | 缺失 → 🔴 **FAIL**(5/14 教训) |
| Gate 3 瓶颈 | 决策日志有"瓶颈定价潜力"评级 | 缺失 → ⚠️ |
| Gate 4 反方 | 信号行有"反方观点"列且非空 | 缺失 → 🔴 **FAIL** |

**加减仓信号检查**(signal-rebalance 走的):

| Gate | 检查项 | 失败标准 |
|------|--------|---------|
| Gate 1 技术面(加仓/减仓时) | 信号行有 RSI/MACD/%B + "vs 原开仓" 比较 | 缺失 → ⚠️;止损止盈可跳 |
| Gate 2.5 可交易性 | 调整后单票占比 + 主线集中度 + 净赔率/止盈 | 缺失 → 🔴 **FAIL** |
| Gate 4 反方 | 反方观点列非空 + 4 类问题至少 2 类 | 缺失 → 🔴 **FAIL** |

### Check 2b: P3.0 触发器扫描是否跑

读决策日志"今日触发器扫描"段:
- 段缺失 → 🔴 **FAIL**(daily-briefing P3.0 漏跑 price-trigger-watch)
- 段存在但 0 命中 0 失效 0 未触发 → ⚠️(可能 watchlist 为空,核对 positions.md)
- 命中标的未进 P3.2 走 signal-generation → 🔴 **FAIL**
- 失效标的未从 positions.md 关注清单删除 → ⚠️ 列出待清理项

### Check 3: 每个候选标的是否走了 signal-generation

每个新信号必须能在决策日志找到对应的 4-Gate 输出块。**找不到 → 🔴 信号未经过 pipeline,撤回或补做**。

### Check 4: knowledge/ 更新是否被遗漏

根据当日 `reports/YYYY-MM-DD.md` 内容判断是否触发更新条件(详见 CLAUDE.md "Knowledge Update Triggers"):

| 报告含关键词 | 应更新文件 | 检查 |
|-------------|-----------|------|
| Fed/PBOC 利率变化 / 新制裁/关税 / 地缘升级 / 数据 surprise | `knowledge/context.md` | 当日 git status 应显示 modified |
| 重大模型/芯片/资本支出新闻 | `knowledge/ai-landscape.md` | 同上 |
| 新板块/标的发现 | `knowledge/watchlist-sectors.md` | 同上 |

漏更新 → ⚠️ 列出建议更新项

### Check 5: 数据警示 / fallback 记录

- 当日 session 任何工具失败/限流/Playwright fallback 必须在 `decisions/YYYY-MM-DD.md` 的"数据警示"区记录
- 报告中标 "via Playwright fallback" 的数据点必须在决策日志对账
- 缺失 → ⚠️

### Check 6: 单一事实源(SSOT)— 防文档漂移 ⭐

读 `decisions/positions.md` 拿到所有持仓标的的"当前价",然后:

1. **grep 所有文件**中该标的的价格出现:`grep -rn "标的代码\|标的名" knowledge/ research/ reports/ decisions/`
2. **逐个比对**与 positions.md 的价格
3. **不一致判定**:
   - 该价格**没标日期戳**(如"¥17.72")→ 🔴 **FAIL**(可能被未来读者误用)
   - 该价格**标了日期但已 >3 天**(如"5/8 ¥17.65")→ ⚠️ 提示考虑删除
   - knowledge/watchlist-sectors.md 或 research/INDEX.md 中价格不带日期戳 → 🔴 **FAIL**(只能放冻结快照)
4. **必修项**:positions.md 是唯一活价格源,其他位置必须 `[详见 positions.md]` 或 `¥X (YYYY-MM-DD 调研冻结)`

详见 CLAUDE.md "🗂 单一事实源(SSOT)— 防文档漂移"。

### Check 7: Playwright 浏览器残留检查 ⭐

**触发**:本日 session 是否调用过 Playwright 工具(`mcp__playwright__browser_*`)。

1. grep TodoWrite 历史 + 工具调用日志,统计 `browser_navigate` 调用次数 N
2. 统计 `browser_close` 调用次数 M
3. **判定**:
   - M >= N → ✅ 全部关闭
   - M < N → 🔴 **FAIL** 残留 (N - M) 个未关浏览器 → **立即调用 `browser_close`** 直到 0
4. **不是预防性 close,是事后审计** — 每次用完应当时关,这里只是兜底

详见 [tool-fallback skill](../tool-fallback/SKILL.md) "用完必关闭浏览器"。

### Check 8: Stale 检测命中是否 Playwright fallback

**触发**:本日 Yahoo 拉数据时是否出现 stale(`regularMarketTime` 落后 BJT >15min / 跨市场分界 / >15:15 仍 REGULAR)。

1. 复盘工具调用,看是否有 stale 信号
2. **若有 stale → 必须有对应 Playwright fallback 调用** + 对应数据点标注"东方财富 BJT XX:XX 实测"
3. **判定**:
   - stale 有 / Playwright fallback 有 / 数据标注有 → ✅
   - stale 有 / 但用了 stale 数据下结论 → 🔴 **FAIL**
   - stale 有 / Playwright 拉了但没标注来源 → ⚠️

## 输出格式

append 到 `decisions/YYYY-MM-DD.md` 末尾:

```markdown
---

## 🔍 Briefing Audit (auto by briefing-audit skill)

### Check 1: 17 步执行
- [✅/🔴] 全部 completed / 缺失: [列表]

### Check 2: 4 道闸(每条信号)
| 信号 | Gate1 技 | Gate2 Kelly | Gate3 瓶颈 | Gate4 反方 |
| 太极 | ✅ | ✅ | ✅ | ✅ |
| 昊华 | ⚠️ 无 | ✅ | ✅ | ✅ |
...

### Check 3: signal-generation pipeline
- [✅/🔴] 所有信号都有 4-Gate 输出 / 漏: [列表]

### Check 4: knowledge/ 更新
- [✅/⚠️] 完整 / 建议更新: [文件列表 + 原因]

### Check 5: 数据警示
- [✅/⚠️] 完整 / 缺失记录: [fallback 列表]

### Check 6: SSOT 漂移
- [✅/🔴] 价格唯一源 / 漂移点: [文件:行]

### Check 7: Playwright 浏览器残留
- [✅/🔴] navigate=N / close=M / 残留=(N-M) — 已强制 close

### Check 8: Stale → Playwright fallback
- [✅/🔴/⚠️] stale 命中 X 次 / fallback X 次 / 全部标注来源

### 总评
- 🟢 全部通过 / 🟡 N 项警告 / 🔴 N 项失败必须修正
- **下次改进点**:[针对失败项的 actionable 改进]
```

## 失败处理

- 🔴 FAIL 项 → 主流程必须修正后才能结束
- ⚠️ 警告项 → 当下记录,下次 briefing 优先处理

## Anti-pattern

❌ 不要把 audit 当形式主义跳过
❌ 不要为了"全 ✅"修改判定标准
✅ Audit 失败是健康信号,说明流程在保护你
