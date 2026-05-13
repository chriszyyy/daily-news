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

### Check 2: 4 道闸是否全过(每条新信号)

读 `decisions/YYYY-MM-DD.md` "今日发出的信号" section,对每条信号检查:

| Gate | 检查项 | 失败标准 |
|------|--------|---------|
| Gate 1 技术面 | 信号行有"赔率"列且非空 | 缺失 → ⚠️ |
| Gate 1 **4 维位置** | 信号有 52w+区间分位/近20日/近5日/放量 4 数 | 缺失 → 🔴 **FAIL** |
| Gate 1 **滞涨标签校验** | 若信号叙事含"滞涨/认知差/未被定价",4 维任一阈值命中(近5日>10% / 近20日>15% / 距52w高<15% / 放量) → 标签必须取消 | 未取消 → 🔴 **FAIL**(国茂 5/12 教训) |
| Gate 2 Kelly | 信号行有"Kelly仓位"列且非空 | 缺失 → ⚠️ |
| Gate 3 瓶颈 | 决策日志有"瓶颈定价潜力"评级 | 缺失 → ⚠️ |
| Gate 4 反方 | 信号行有"反方观点"列且非空 | 缺失 → 🔴 **FAIL** |

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
