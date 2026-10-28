# Improve with Ola — 计划

> v1.3 · 2026-10-20 · 已按今天讨论收敛；只保留最终决定，待定项见 §8。未开始开发。（v1.3：阶段改为 vertical（V1 单维）→ V2 → horizontal；v1.2：量化目标加 turns、tool calls 两维，latency 降为参考；v1.1：reflection = HL task、automation 改动清单）

## TL;DR

用 GEPA 优化 automation 的 instruction：固定任务 + 程序化打分 + 完整 feedback 交给 reflection LM 生成候选 → 候选在同一路径重跑 → Pareto 选择 → held-out 验证 → 人工采用。**全部在 HL harness 内自包含**（执行、evaluator、reflection 都走 HL 自己的模型路径，不经 Devin）。VM 上起一个 HL 实例 + 测试 org 跑；三个场景 C1/C2/C3 已定。

下一步：S1（VM 起实例、关 mem0、加 instruction 版本表、跑 C1 baseline），然后 V1：C1 只优化 quality。

## 1. 已定的决策

| 项 | 决定 |
|---|---|
| 优化对象 | automation 的 instruction（`automations.goal`）。任务目标、答案、评分、权限、环境不动 |
| 产品入口 | 入口 prompt 固定（参考 Improve with Devin 那句）；GEPA 是后面的实验/候选引擎，和入口分开 |
| 三个场景 | C1 冻结 repo 事实问答 / C2 CSV 对账 / C3 GitHub 周活动报告（任务卡：`gepa-c1/c2/c3-task-card.md`） |
| 打分 | 全部程序化、确定性；agent 输出固定 JSON；LLM 不打分 |
| ASI / feedback | = evaluator 返回的 feedback 文本（GEPA 论文 μ_f）：对错、正确答案、差异明细、执行 trace 摘录（工具调用序列、读过的文件、回答全文）。**evaluator 不诊断，诊断是 reflection LM 的事**。含正确答案（GEPA 默认做法） |
| 防 overfit | train / val(D_pareto) / held-out test 三份；test 换分布（C1 换 repo，C2 换 schema+seed 段，C3 换窗口+repo）；每样例 k=3；候选 prompt 含 train 具体事实只记录不拒绝 |
| 模型 | 执行 = Ola 自己的模型路径；evaluator 无 LLM；**reflection_lm = 一个 HL task**（goal = GEPA meta-prompt，不给工具，输出即新 instruction）——不需要单独 LLM，harness 只多一种固定的"反思 instruction"。具体模型名实验内固定 |
| 环境 | Devin VM 上一个 HL 实例 + 测试 org，真实模型、真实 Langfuse；之后搬集群测试 org |
| 版本控制 | instruction 版本表 + 执行时选版本；候选跑的时候不覆盖生效版本 |
| mem0 | 实验实例**关掉**长期记忆（否则第二次跑同题会从记忆拿上次答案，环境不固定）。mem0 后续会拆出去，开关从 main 直接做 |
| 成本 | USD / tool calls / 时长 作为 GEPA `objective_scores`，不进主 score |

## 2. 闭环

```text
任务卡（冻结数据 + evaluator）
        ↓
instruction v_i ──runner──▶ HL automation 路径跑一次（新 task session，mem0 关）
        ↓                      → tasks 行 + Langfuse trace + usage
evaluator：score + feedback(ASI) + objective_scores
        ↓
GEPA：reflective dataset → reflection_lm → 候选 v_j
        ↓
候选同样例重跑 → minibatch 比较 → val 上 Pareto 选择
        ↓
预算用完 → held-out test → 前后对照 → 人工决定是否采用
```

## 3. 三个场景（已定，细节见任务卡）

| | 数据 | 样例 | score | objective |
|---|---|---|---|---|
| C1 | `openai/openai-agents-python` pin v0.24.0 (`17d994b`)，`src/agents/` 范围 20 题；test 换 pydantic-ai 或 adk-python 10 题 | 20 + 10 | answer 规范化匹配 ∧ path 相等 → 0/1 | USD、读文件次数、时长 |
| C2 | `gepa-c2/gen.py <seed>` 生成报销单 vs 账本两份 CSV，埋 3–8 处不一致；test 换 seed 段 + 列名/多货币列/行数翻倍 | ~20 + 8 | 两 total 对 ∧ mismatch_ids 集合全对 → 0/1（辅助 0.4·total_ok + 0.6·F1） | USD、Python 执行次数、时长 |
| C3 | 上游 repo 历史周窗口，`gepa-c3/snapshot.py` 冻结时抓 gold（新开 issue + 非 bot 合并 PR，按编号）；test 用 pydantic-ai 两窗口 | 6 + 2 | mean(issue_F1, pr_F1)；summary 不打分 | USD、tool calls、时长 |

fork 到 SeekMi org 被 App token 403 挡住 → 先 pin 上游 SHA（不可变，实验等价）。

## 4. 怎么 code：直接用现有 harness

原则：不另起 runner 服务；GEPA 相关代码是 HL 里的一个包 `src/hidden_layer/improve/`，复用 automation → tasks → pipeline → Langfuse 这条已有链路。

### 4.1 现有链路（已读代码确认）

- automation 是 `automations` 表一行；`dispatch._fire()` 读行后 `enqueue(goal=row["goal"], automation_id=..., model_override=row["model"], origin="automation")` 产生一条 `tasks` 行，worker 用 `GOAL` 渲染 prompt 跑（`pipeline.py:901`）。
- `tasks.trace_id` 关联 Langfuse trace；`usage_events_local` 按 trace_id 记 token/费用（`tasks.list_automation_runs` 已经这样 JOIN）。
- `trace.record_score()` 已能往 Langfuse trace 写 score（注释里就写着 "GEPA training signal"）。
- Langfuse key 在 settings（`langfuse_public_key/secret_key/host`），实例自己的 tracing 项目。
- mem0：`app.py` 无条件构造 `Mem0LongTerm`，**没有关闭开关**；`LongTermMemory` 是 Protocol。
- `prune_automation_rows` 会删旧 task 行 → 实验数据不能只靠 tasks 表。

### 4.2 要加的东西

| # | 改动 | 位置 | 大小 |
|---|---|---|---|
| 1 | mem0 开关：`memory_backend: "mem0" \| "off"`，off 时注入 `NullLongTerm`（recall 返回空、record no-op） | `config.py`、`memory/null_backend.py`（新）、`app.py` | 小 |
| 2 | instruction 版本表 `automation_instruction_versions(id, automation_id, parent_id, text, label, created)`；`tasks` 加 `instruction_version_id`；`enqueue()` 接受 `goal`+`instruction_version_id`，`_fire` 用当前生效版本 | `db.py`/alembic、`dispatch.py` | 小–中 |
| 3 | runner：`improve/runner.py` —— `run(automation_id, version_id, example) -> RunRecord`：按版本 `enqueue`（样例输入放 payload），等 task 终态，取 `trace_id`，从 Langfuse 拉 trace（工具调用、读的文件、最终输出）和 usage | `improve/runner.py`（新） | 中 |
| 4 | 实验记录表 `improve_runs(id, task_id, version_id, example_id, split, score, feedback, objective_json, trace_id, created)`，不受 prune 影响 | `db.py`/alembic | 小 |
| 5 | evaluator：每场景一个 `evaluate(example, final_output, trace) -> (score, feedback, objective_scores)`；feedback 按 §1 定义拼全量证据 | `improve/evaluators/c1.py c2.py c3.py`（新） | 中 |
| 6 | GEPA adapter：`evaluate(batch, candidate)` = 对 batch 每个样例调 runner+evaluator；`make_reflective_dataset` = `{Inputs, Generated Outputs, Feedback}`；`reflection_lm` = 包一层 HL 的模型调用（和 commander 同一 provider/key） | `improve/gepa_adapter.py`（新），依赖 `gepa` 库 | 中 |
| 7 | 实验入口：`hl improve run --scenario c1 --budget N` CLI；结果导出 json/markdown | `cli.py` | 小 |
| 8 | Langfuse 读取：用 Langfuse SDK 按 trace_id 拉 observations（不用旧 `langfuse_mcp.py` 搜索式工具） | `improve/trace_pull.py`（新） | 小–中 |

不做：版本管理 UI、自动替换生效版本、集群部署、Improve with Devin 式入口 prompt 的 agent 工具（S5）。

### 4.3 环境固定项

repo commit、样例输入、runtime 版本、模型名+参数、工具集（C1 GitHub 只读；C2 Python 沙盒+附件；C3 GitHub 只读）、权限、evaluator 版本、mem0 off、每 run 新 task session。LLM 本身不确定 → k=3。

### 4.4 量化目标：performance / cost / latency / turns / tool calls（GEPA 源码确认）

每个指标按"一次 run"定义，候选层面在 val 集上按题 k=3 取均值再对题平均。

| 指标 | 一次 run 的定义 | 来源 | 给 GEPA（higher is better） | 报告里报 |
|---|---|---|---|---|
| performance（主分） | C1 answer∧path → 0/1；C2 total 对∧mismatch 集合全对 → 0/1；C3 mean(issue_F1, pr_F1)；格式错/超时/报错 = 0 | evaluator | `quality` 原值 | 均值 + pass^3（三次全对比例，不进 GEPA） |
| cost | 该 run trace 下所有 LLM generation 的 USD 之和（含 guardrail；mem0 off 无记忆调用）；失败 run 照算 | `usage_events_local` 按 trace_id | `economy = 1/(1+cost_usd)` | USD 均值、相对 baseline 倍数 |
| latency | `tasks.finished − tasks.started`（排除排队）；超时记上限 | tasks 表 | `speed = 1/(1+latency_s)`（受网络影响，降为参考） | 秒 中位数 + p90 |
| no. of turns | commander 的 LLM generation 次数（每轮 模型→工具→模型 = 1 turn） | Langfuse trace generation span 数 | `turns_eff = 1/(1+turns)` | 均值 + p90 |
| no. of tool calls | trace 里 tool-call span 数（C1 另记 读文件/列目录 两列做诊断） | Langfuse trace tool span 数 | `tools_eff = 1/(1+tool_calls)` | 均值 + p90 |

- `evaluate()` 每样例返回 `score`（= quality）和 `objective_scores={"quality","economy","speed","turns_eff","tools_eff"}`；`frontier_type="hybrid"`（按样例 + 按目标），每个维度上最优的候选都留在池里。
- 注意：**候选接受（minibatch 上 sum(score) 要超过父代）只看主分**，其余四个只影响谁留在 frontier 和被选去变异。如果要"同质量更便宜/更少 turn"也能被接受，要么主分用 `quality − λ·cost_norm`，要么注入自定义 `acceptance_criterion`（`strategies/acceptance.py` Protocol）。V1 只用主分 = quality，不传 objective_scores；V2 起才引入 λ / acceptance（D3）。
- 不进候选 objective、单独记"优化总开销"：reflection task 的 cost/latency、评分脚本、失败重试。

### 4.5 automation 要改的（只这些）

1. `dispatch.enqueue()` 加 `instruction_version_id`；`_fire` 用生效版本，runner 可传任意版本（不动 `automations.goal`）。
2. 新表 `automation_instruction_versions`；`tasks` 加 `instruction_version_id` 列。
3. 样例输入走 task payload（现有 `trigger_json`/payload 字段）。
4. `improve_runs` 表避开 `prune_automation_rows`。
5. 测试 org 的三个 automation 不挂 schedule，只由 runner 触发。

调度器、webhook door、worker、pipeline、trace 不动。

## 5. 阶段：先 vertical 再 horizontal

实验大方向：先在一个场景上证明能优化**一个**维度，再加维度、再加场景。五维指标（§4.4）从 S1 起全部记录，但只有当前阶段的维度进优化。

| 阶段 | 做什么 | 完成标准 |
|---|---|---|
| S0 ✅ | 三张任务卡 + 数据脚本 | 不用优化器也能判一次 run 好坏 |
| S1 | VM 起 HL 实例+测试 org；改动 #1 #2 #4 #8；C1 跑 baseline（20 题 × k=3）；五维全记 | 能回答"哪个版本、哪题、做了什么、花了多少、几 turn、几次 tool call"；数据不被 prune |
| **V1** | C1 只优化 quality：GEPA 默认（主分 = quality，不传 objective_scores，frontier 按样例）；改动 #5 #6 #7；有限预算 | held-out（第二个 repo）quality > baseline 且差值 > k=3 噪声；记录优化总开销；人工看候选 instruction 用了哪些 feedback。分支：baseline quality 已 >90% → 维度换成 tool calls（quality ≥ baseline 作约束） |
| **V2** | C1 第二维度：固定 quality 不降，优化 tool calls（或 cost，看 V1 数据定）；主分 `quality − λ·x` 或自定义 acceptance | quality 不低于 V1 结果，目标维度显著下降 |
| **H** | runner/adapter 不改代码，C2、C3 各跑一遍 V1；最后 hybrid frontier 多维一起跑 | 三场景前后对照表 + Pareto 图 + 候选 diff + 采用/拒绝理由 |
| S5 | 集群测试 org、真实 cron/webhook、版本 UI、发布/回滚 | 实验反馈后定 |

## 6. Demo

三个场景同一闭环；现场展开一个：初始 instruction → baseline trace/cost → feedback → 候选 diff → 重跑/val → held-out → 采用/拒绝。数字全部实测，不预设提升；正确拒绝劣化候选同样算闭环有效。单次运行成本和优化总成本（含 reflection、失败重试）分开列。

## 7. 现状 vs 缺口

| 能力 | 现状 | 缺口 |
|---|---|---|
| automation 执行 | 有完整链路 (`_fire`→`enqueue`→worker→trace) | 按版本/样例触发（#2 #3） |
| instruction 版本 | 只有 `automations.goal` 一列 | 版本表（#2） |
| trace / 成本 | trace_id + usage 已关联 | 拉 observations（#8） |
| judge / feedback | `record_score` 可写分 | 三个 evaluator（#5） |
| GEPA | 无 | adapter（#6） |
| mem0 | 无开关 | `off`（#1） |
| 实验记录 | tasks 会被 prune | `improve_runs`（#4） |

## 8. 待定

| ID | 问题 | 何时 |
|---|---|---|
| D3 | V1 预算（metric calls 上限）、停止条件、train/val 比例；V2 选 tool calls 还是 cost、λ | V1 前 / V2 前 |
| D6b | 执行模型与 reflection_lm 具体模型名 | S1 前 |
| D7 | demo 之后"采用新版"做到哪一步（只展示 vs 一键写回 goal） | H 前 |
| D8 | C3 held-out 窗口的最终选择 | H 前 |

## 参考

- [本次讨论](https://app.devin.ai/sessions/9a3ad6b720c8479fa345f2fd39e1576b)
- [GEPA 论文](https://arxiv.org/abs/2507.19457) §3 feedback function μ_f；[adapter 源码](https://github.com/gepa-ai/gepa/blob/main/src/gepa/core/adapter.py)；`default_adapter.py` `ContainsAnswerEvaluator`；`strategies/instruction_proposal.py` meta-prompt
- 代码：`runtime/dispatch.py`（`_fire`/`enqueue`/`add_automation`）、`tasks.py`（`list_automation_runs`/`prune_automation_rows`）、`trace.py`（`record_score`）、`app.py`（mem0 构造）、`memory/base.py`（`LongTermMemory` Protocol）
