# C2 任务卡 — 费用对账（草稿 v0.1，2026-10-20）

## 冻结环境
- 数据由 `gepa-c2/gen.py <seed> <outdir>` 确定性生成；seed 固定即数据固定
- 每个样例两份 CSV：`expense_report.csv`（员工报销）、`ledger.csv`（财务系统），40–60 行，列：expense_id, employee, date, category, amount
- 埋 3–8 处不一致，四类：`amount_diff` / `missing_in_ledger` / `missing_in_report` / `category_diff`
- 标准答案 `gold.json`：report_total、ledger_total、mismatch_ids（+ kind）
- 工具：只给 Python 沙盒 + 附件读取（不给 web / GitHub）
- test 换分布：test 集的 seed 用另一段范围，并换列名 / 多一列 currency / 行数翻倍（gen.py 加 `--variant` 实现，待做）

## 输出格式
```json
{"report_total": 19107.55, "ledger_total": 18833.22, "mismatch_ids": ["EXP-001-008", ...]}
```

## 初始 instruction v0
> 你是财务对账助手。附件有两份 CSV：员工报销单和财务账本。请核对两者，报告两边各自的总金额，以及所有不一致的 expense_id。最后以 JSON 输出：`{"report_total", "ledger_total", "mismatch_ids"}`。

## evaluator（确定性）
- `format`：JSON 可解析且三个键齐全，否则 0 分，ASI="format"
- `total_ok`：两个 total 与 gold 误差 ≤ 0.01
- `set_f1`：mismatch_ids 与 gold 的 F1；`set_exact` = F1==1
- score（主）= 1 若 total_ok 且 set_exact，否则 0；score（辅，用于 ASI 和分析）= 0.4·total_ok + 0.6·F1
- 成本 objective：USD、python 执行次数、wall_seconds
- Feedback（交给 reflection LM）：对/错；gold 的两个 total 与 agent 的差值；漏报 / 误报的 expense_id 及其 kind（直接给 gold mismatches）；执行 trace 摘录——是否运行了 Python、代码正文、报错输出、最终回答全文

## 样例
| seed | rows | mismatches | 用途 |
|---|---|---|---|
| 1 | 44 | 5 | train |
| 2 | 41 | 7 | train |
| 3 | 47 | 8 | train |
| 4–8 | — | — | train / val |
| 101–106（variant） | — | — | held-out |

## 待定
- variant 具体改什么（列名 / 货币列 / 行数）
- 是否允许 agent 把结果写回附件（当前只要求 JSON）
