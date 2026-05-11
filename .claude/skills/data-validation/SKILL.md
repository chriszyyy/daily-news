---
name: data-validation
description: 启动独立验证 subagent 交叉验证 session 中的关键数据。daily workflow step 15、用户质疑数据准确性、信号 finalize 之前使用。验证价格/财报/事实声明三类数据，三级评级（✓已验证/⚠存疑/✗错误）。
---

# 数据验证

## Contract

- **Triggers**: daily-briefing P3.4 / 用户质疑数据准确性 / 信号 finalize 之前
- **Inputs**: 待验证的价格/财报/事实声明列表
- **Outputs**: 验证报告(✓已验证 / ⚠存疑 / ✗错误)
- **Calls**: 启动独立 subagent(general-purpose, run_in_background: true)
- **Called by**: `daily-briefing`(P3.4 background)、用户

启动独立验证 subagent(`run_in_background: true`),交叉验证本次 session 所有关键数据。

## 验证维度

1. **价格/估值准确性** — Yahoo Finance 重新拉取
2. **财报数据一致性** — Yahoo `get_financial_statement` 重查
3. **新闻事实真实性** — Exa 二次搜索（≥2 个独立来源）
4. **供应链关系可信度** — Exa 验证客户/供应商关系
5. **数据时效性** — 检查时间戳，>7 天标"可能过时"

## 评级体系

| 评级 | 含义 | 处理 |
|------|------|------|
| ✓ | 已验证 | 信号可用 |
| ⚠ | 存疑/修正（仅 1 来源 / 数字差异） | 信号中标注"⚠未充分验证" |
| ✗ | 错误/过时 | 修正数据，回滚信号 |

## Agent Prompt 模板

启动验证 agent 时使用以下 prompt 结构（用 Agent 工具，subagent_type=general-purpose）：

```
你是数据验证 agent。请独立验证以下数据点的准确性。不要信任已有结论，用工具重新查询验证。

**价格数据**：
[列出所有报告中引用的股价、指数、商品价格及其 ticker]

**财报声明**：
[列出关键财报数字，如 "XX 公司 Q1 营收 +49%"、"净利润 +262%"]

**事实声明**：
[列出定性声明，如 "XX 是 YY 的唯一供应商"、"市占率 >75%"、"交付周期 >24 个月"]

验证方法：
1. 用 Yahoo Finance get_stock_info 重新拉取每个 ticker 的当前价格，对比报告数字
2. 用 Yahoo Finance get_financial_statement（quarterly_income_stmt）验证财报数字
3. 用 Exa 搜索验证每个事实声明（至少找到 2 个独立来源才标 ✓）
4. 检查所有数据时间戳，标记 >7 天为"可能过时"

输出格式：
## 数据验证报告
### ✓ 已验证
- [数据点] — [验证来源]

### ⚠ 存疑/修正
- [数据点] — [问题描述：仅 1 来源 / 数字差异 报告 X vs 实际 Y]

### ✗ 错误/过时
- [数据点] — [错误描述+正确数据]
```

## 关键时序

**必须在 finalize signals 之前 review 验证结果**：
- ✗ 项 → 修正数据 + 撤回相关信号
- ⚠ 项 → 在信号中标注不确定性（信心降级）
- ✓ 项 → 信号可入库

## 启动方式

用 Agent 工具，`run_in_background: true`，等其他工作完成后取回结果。验证 agent 不应阻塞主流程。
