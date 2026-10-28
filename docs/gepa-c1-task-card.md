# C1 任务卡 — Repo 事实问答（草稿 v0.1，2026-10-20）

## 冻结环境
- Repo: `openai/openai-agents-python`
- Pin: tag `v0.24.0` = commit `17d994bd3045dae71acda676a4ef4762ed8ecd94`（答案全部按此 commit 核）
- 注：GitHub App token 不能 fork / 建 org repo（403）。先直接 pin 上游 SHA（commit 不可变）；如果要 org 内 fork，需要 Yuandong 用自己账号 fork 一下。
- 范围：只问 `src/agents/`（320 个 .py，约 26k 行）
- 工具：GitHub 只读（tree + 读文件），无代码搜索
- test 集第二个 repo（待定）：`pydantic/pydantic-ai` 或 `google/adk-python`（同为 Python agent 框架，同题型）

## 输出格式（agent 必须输出，否则 0 分）
```json
{"answer": "<短答案>", "path": "src/agents/xxx.py"}
```

## 初始 instruction v0（故意朴素）
> 你是代码库问答助手。给定 GitHub repo `openai/openai-agents-python`（commit 17d994b）和一个问题，用 GitHub 工具阅读代码并回答。最后以 JSON 输出：`{"answer": ..., "path": ...}`，path 为答案所在文件相对路径。

## evaluator（确定性）
- `format`: 能解析出 JSON 且含 answer/path → 否则 score 0，ASI="format"
- `answer_ok`: 规范化（去空白 / 引号 / 大小写、`100_000`=`100000`、`1 GiB`=`1073741824`）后精确匹配 gold；集合题按集合相等
- `path_ok`: path == gold path（路径题也可给多个可接受 path）
- score = 1 仅当 answer_ok 且 path_ok；否则 0（可选：answer 对 path 错给 0.5，待定）
- 成本 objective：USD、tool_calls、wall_seconds（从 Langfuse trace）
- Feedback（GEPA reflective dataset 记录，交给 reflection LM；evaluator 不做诊断）：
  - Inputs：问题原文
  - Generated Outputs：agent 最终回答全文（含 JSON）
  - Feedback 文本：对/错；正确答案与正确 path；agent 给的 answer/path 差在哪；执行 trace 摘录——工具调用序列、读过的文件列表（含是否读过 gold path）、读文件次数、成本
  - 不裁剪成标签；由 reflection LM 自己归因

## 题目（gold 已按 v0.24.0 核对；T=train V=val H=held-out，划分待定）

| # | 题 | gold answer | gold path | 类型 |
|---|---|---|---|---|
| 1 | `DEFAULT_MAX_TURNS` 的值是多少？ | 10 | src/agents/run_config.py | 默认值 |
| 2 | `DEFAULT_MAX_ARCHIVE_MEMBERS` 的值？ | 100000 | src/agents/run_config.py | 默认值 |
| 3 | `DEFAULT_MAX_ARCHIVE_INPUT_BYTES` 等于多少字节？ | 1073741824 | src/agents/run_config.py | 默认值 |
| 4 | `RunConfig.pre_approval_tool_input_guardrails` 默认值？ | False | src/agents/run_config.py | 默认值 |
| 5 | `RunConfig.max_function_tool_concurrency` 默认值？ | None | src/agents/run_config.py | 默认值 |
| 6 | run state 的 `CURRENT_SCHEMA_VERSION` 是多少？ | 1.21 | src/agents/run_state.py | 默认值 |
| 7 | `SQLiteSession.__init__` 的 `db_path` 默认值？ | :memory: | src/agents/memory/sqlite_session.py | 默认值 |
| 8 | `SQLiteSession` 默认的 `messages_table` 表名？ | agent_messages | src/agents/memory/sqlite_session.py | 默认值 |
| 9 | `SQLiteSession` 直接继承哪个类？ | SessionABC | src/agents/memory/sqlite_session.py | 定义 |
| 10 | `ToolContext` 直接继承哪个类？ | RunContextWrapper | src/agents/tool_context.py | 定义 |
| 11 | `Handoff` 类定义在哪个文件？ | （path 即答案） | src/agents/handoffs/__init__.py | 定位 |
| 12 | `RunResult` 类定义在哪个文件？ | （path 即答案） | src/agents/result.py | 定位 |
| 13 | `OpenAIResponsesModel` 定义在哪个文件？ | （path 即答案） | src/agents/models/openai_responses.py | 定位 |
| 14 | `trace()` 函数定义在哪个文件？ | （path 即答案） | src/agents/tracing/create.py | 定位 |
| 15 | `set_tracing_disabled` 定义在哪个文件？ | （path 即答案） | src/agents/tracing/__init__.py | 定位 |
| 16 | 顶层 `agents.set_default_openai_key` 把实现委托给哪个模块？ | src/agents/_config.py | src/agents/__init__.py | 调用链 |
| 17 | `ModelRetryBackoffSettings` 有哪 4 个字段？ | {initial_delay, max_delay, multiplier, jitter} | src/agents/retry.py | 集合 |
| 18 | `exceptions.py` 中直接继承 `AgentsException` 的类有几个？ | 11 | src/agents/exceptions.py | 计数 |
| 19 | `src/agents/` 下有几个文件引用了 `handoff_input_filter`？ | 6 | src/agents/run_config.py（可接受任一引用文件） | 跨文件 |
| 20 | `Usage` 数据类的 `requests` 字段默认值？ | 0 | src/agents/usage.py | 默认值 |

题型分布：默认值 10、定位 5、定义 2、调用链 1、集合 1、计数 1、跨文件 1。
跨文件 / 计数题（18、19）最难，正好区分 "只读一个文件" 和 "系统地搜" 的 instruction。

## 待定
- 划分：建议 T 8 / V 6 / H 6；H 里偏放难题（跨文件、计数）
- 第二个 repo 的 held-out 题（同题型 10 道）
- k=3 重复；总预算（每轮 run 数上限）
- 需要 Ola 侧：测试 org 的 GitHub Composio 连接只读授权到该 repo
