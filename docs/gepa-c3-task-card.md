# C3 任务卡 — GitHub 周活动报告（草稿 v0.1，2026-10-20）

## 冻结环境
- Repo：上游 `openai/openai-agents-python`（fork 不带 issue，所以指向上游）
- 窗口：固定的历史周（周一 00:00Z 起，7 天）；活动量：每周约 20 个 issue、非 bot 合并 PR 约 40–60 个
- gold 由 `gepa-c3/snapshot.py` 在冻结时刻从 API 抓一次存成 json，之后 evaluator 不再查 GitHub；issue/PR 编号和创建/合并时间不可变，标题被改也不影响（按编号打分）
- 工具：GitHub 只读（Composio：list issues / list PRs / 读 issue），不给 web
- 排除 `dependabot[bot]` 等 bot PR（否则一周 100+ 条，报告没意义）
- test 换分布：held-out 用 `pydantic/pydantic-ai` 的两个周窗口（同 snapshot 脚本）

## 输出格式
```json
{"issues_opened": [4201, 4207, ...], "prs_merged": [4190, ...], "summary": "<自由文本，不打分>"}
```

## 初始 instruction v0
> 你是 repo 周报助手。对 `openai/openai-agents-python`，统计 {start} 到 {end}（UTC）之间新开的 issue 和已合并的 PR（排除 bot），写一段简短周报，并以 JSON 输出 issue 编号列表和 PR 编号列表。

## evaluator（确定性）
- `format`：JSON 可解析且两个列表齐全，否则 0 分
- `issue_recall / issue_precision`、`pr_recall / pr_precision`：编号集合 vs gold
- 编造 = 不在 gold 里的编号（窗口外、或根本不存在）
- score = mean(issue_F1, pr_F1)；可选阈值版：F1 ≥ 0.95 记 1，否则 0
- summary 不打分（只给人看），避免 judge 噪声进 frontier
- 成本 objective：USD、tool_calls（list 调用次数）、wall_seconds
- Feedback（交给 reflection LM）：对/错；gold 列表 vs agent 列表的差集（漏报编号、误报编号，并标注误报是 bot PR / 窗口外 / 不存在 / issue-PR 混淆）；执行 trace 摘录——GitHub 工具调用序列与参数（翻页、过滤条件）、最终回答全文；不预先归因，由 reflection LM 判断

## 窗口（草案）
| 周起（UTC） | 用途 | issues | non-bot PRs merged |
|---|---|---|---|
| 2026-08-24 | train | 44 | — |
| 2026-09-07 | train | 17 | — |
| 2026-09-14 | train | 23 | 36 |
| 2026-09-21 | val | 18 | — |
| 2026-09-28 | val | 17 | 45 |
| 2026-10-05 | held-out | 26 | — |
| pydantic-ai × 2 周 | held-out（换 repo） | — | — |

（issues 数来自 10-20 的一次扫描；最终以 snapshot 冻结结果为准）

## 待定
- 是否要求按 label 分组（增加难度；gold 已含 labels）
- "已合并 PR" 还是 "新开 PR"（合并更能体现翻页 + 过滤 bot 两个坑）
- Composio GitHub toolkit 是否有 list PRs with merged_at 字段；若没有要用通用 GitHub MCP
