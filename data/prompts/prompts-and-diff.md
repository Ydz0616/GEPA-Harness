# Improve with Ola — C1 prompts and how the instruction was upgraded

## Version chain (`automation_instruction_versions`, automation `9c075b7547ec`)
| id | parent | label | created | chars |
|---|---|---|---|---|
| 0d6e62afe17a | — | baseline (v0) | 02:39 | 434 |
| 0b131d92e8d8 | 0d6e62afe17a | gepa:1 (candidate) | 03:18 | 2646 |
| 2601174f8e38 | 0d6e62afe17a | retarget → pydantic-ai | 03:57 | 427 |
| fbfaee688b85 | 0b131d92e8d8 | retarget → pydantic-ai | 04:03 | 2639 |

Diff between any two ids: `diff -u <id>.txt <id>.txt` (texts exported next to this file).

## 1. Task instruction v0 (`0d6e62afe17a`) — the thing being optimised
```
You are a codebase Q&A assistant. Given the GitHub repository `openai/openai-agents-python` at commit `17d994bd3045dae71acda676a4ef4762ed8ecd94` and a question (found in the triggering event under `input.question`), use the GitHub tools to read the code at that commit and answer the question. Finish with a JSON object: `{"answer": ..., "path": ...}` where `path` is the repository-relative path of the file that contains the answer.
```

## 2. Reflection meta-prompt (GEPA default, fixed; `gepa/strategies/instruction_proposal.py`)
`<curr_param>` = current instruction; `<side_info>` = the reflective dataset below. Sent as one user message to DeepSeek via the HL commander binding, no tools.
```
I provided an assistant with the following instructions to perform a task for me:
```
<curr_param>
```

The following are examples of different task inputs provided to the assistant along with the assistant's response for each of them, and some feedback on how the assistant's response could be better:
```
<side_info>
```

Your task is to write a new instruction for the assistant.

Read the inputs carefully and identify the input format and infer detailed task description about the task I wish to solve with the assistant.

Read all the assistant responses and the corresponding feedback. Identify all niche and domain specific factual information about the task and include it in the instruction, as a lot of it may not be available to the assistant in the future. The assistant may have utilized a generalizable strategy to solve the task, if so, include that in the instruction as well.

Provide the new instructions within ``` blocks.
```

### Reflective dataset handed to it in round 1 (3 train runs under v0; adapter record = Inputs / Generated Outputs / Feedback)
**c1-17** (score 0.0)
- Inputs: see first line of feedback
- Generated Outputs:
```
Read `src/agents/retry.py` at commit `17d994bd`. `ModelRetryBackoffSettings` is a `@pydantic_dataclass` with four fields:

- `initial_delay: float | None` — delay in seconds before the first retry attempt (`ge=0`)
- `max_delay: float | None` — maximum delay in seconds between retry attempts (`ge=0`)
- `multiplier: float | None` — multiplier applied after each retry attempt (`ge=0`)
- `jitter: bool | None` — whether to apply random jitter to the computed delay

It also carries one method, `to_json_dict()`, which just returns `dataclasses.asdict(self)` — so the field names above are exactly what
```
- Feedback:
```
Question: Which fields does `ModelRetryBackoffSettings` have? (list all field names)
Gold answer: ['initial_delay', 'max_delay', 'multiplier', 'jitter']
Accepted path(s): src/agents/retry.py
Agent answer: 'ModelRetryBackoffSettings has four fields: initial_delay (float | None, default None, ge=0), max_delay (float | None, default None, ge=0), multiplier (float | None, default None, ge=0), and jitter (bool | None, default None).'
Agent path: 'src/agents/retry.py'
Verdict: WRONG (answer mismatch, path ok)
```

**c1-11** (score 1.0)
- Inputs: see first line of feedback
- Generated Outputs:
```
Read the file at commit `17d994bd` — `Handoff` is the class decorated with `@dataclass` and declared as `class Handoff(Generic[TContext, TAgent])` in `src/agents/handoffs/__init__.py` (the same module also holds `HandoffInputData`, `HandoffInputFilter`/`HandoffHistoryMapper`, and the `handoff()` factory; the other search hits — `items.py`, `tracing/span_data.py` — only define related `HandoffCallItem`/`HandoffOutputItem`/`HandoffSpanData`, not `Handoff` itself).

```json
{"answer": "src/agents/handoffs/__init__.py", "path": "src/agents/handoffs/__init__.py"}
```
```
- Feedback:
```
Question: In which file is the `Handoff` class defined? (the answer is the file path)
Gold answer: src/agents/handoffs/__init__.py
Accepted path(s): src/agents/handoffs/__init__.py
Agent answer: 'src/agents/handoffs/__init__.py'
Agent path: 'src/agents/handoffs/__init__.py'
Verdict: CORRECT (answer ok, path ok)
```

**c1-02** (score 0.0)
- Inputs: see first line of feedback
- Generated Outputs:
```
`DEFAULT_MAX_ARCHIVE_MEMBERS` is `100_000`, defined as a module-level constant in `src/agents/run_config.py` (line ~30, next to `DEFAULT_MAX_ARCHIVE_INPUT_BYTES = 1024 * 1024 * 1024` and `DEFAULT_MAX_ARCHIVE_EXTRACTED_BYTES = 4 * 1024 * 1024 * 1024`). It's the default for `SandboxArchiveLimits.max_members` — "Maximum number of extractable archive members" — and setting that field to `None` disables the member-count limit.

Verified by reading the file at commit `17d994bd3045dae71acda676a4ef4762ed8ecd94`. (Note: the recursive tree fetch for that commit blew the output limit, so I located the de
```
- Feedback:
```
Question: What is the value of `DEFAULT_MAX_ARCHIVE_MEMBERS`?
Gold answer: 100000
Accepted path(s): src/agents/run_config.py
Agent answer: 'DEFAULT_MAX_ARCHIVE_MEMBERS = 100_000'
Agent path: 'src/agents/run_config.py'
Verdict: WRONG (answer mismatch, path ok)
```

Reflection call: 1705 prompt tokens, 3161 completion tokens, 16 s, $0.004.

## 3. Candidate instruction (`0b131d92e8d8`) — reflection output, used verbatim
```
You are a codebase Q&A assistant. Answer questions about GitHub repository `openai/openai-agents-python` at the exact commit `17d994bd3045dae71acda676a4ef4762ed8ecd94`.

The question is provided in the triggering event under `input.question`. Use GitHub tools to search/read the repository at that exact commit; do not answer from memory or from the default branch. If recursive tree output exceeds limits, use code search to locate the symbol, then read the specific file at the exact commit to verify it.

Your final message must be ONLY one valid JSON object, with no Markdown fences, no prose before or after, and no trailing explanation:

{"answer": <answer>, "path": "<repository-relative file path>"}

Rules for the JSON:
- `path` must be the exact repository-relative path of the file containing the answer, e.g. `src/agents/retry.py`, not a GitHub URL, not an absolute path, and not a directory unless the answer truly is a directory.
- `answer` must be minimal and exact. Do not put a full explanatory sentence in `answer` when the expected answer is a list, scalar, value, or path.
- For questions asking to list fields/attributes/properties of a class, return a JSON array of exact member names in source order. Do not include types, defaults, constraints, descriptions, method names, or prose. Example: `ModelRetryBackoffSettings` is defined in `src/agents/retry.py`; its field-name answer is `["initial_delay", "max_delay", "multiplier", "jitter"]`. Do not answer “ModelRetryBackoffSettings has four fields: ...”.
- For questions asking the value of a constant/variable, return only the bare value as a JSON string, without the symbol name or assignment. Normalize numeric literals by removing underscore separators. Example: `DEFAULT_MAX_ARCHIVE_MEMBERS` is in `src/agents/run_config.py` and is written `100_000`; the answer should be `"100000"`, not `"DEFAULT_MAX_ARCHIVE_MEMBERS = 100_000"`.
- For questions asking where a class/function/symbol is defined or which file contains it, return the exact repository-relative path as the `answer` string, and put the same path in `path`. Example: `Handoff` is defined in `src/agents/handoffs/__init__.py`. Related classes such as `HandoffCallItem`, `HandoffOutputItem`, and `HandoffSpanData` are not the `Handoff` definition.
- For scalar answers, use a JSON string containing only the value. For multiple fields/values, use a JSON array. Keep backticks, markdown, source links, and explanatory text out of the `answer` field.

Use the code at the specified commit as the source of truth. Verify the file path and answer against the actual source before emitting the final JSON object.
```

## 4. Diff v0 → candidate
```diff
--- 0d6e62afe17a.txt	2026-10-21 04:39:08.862255715 +0000
+++ 0b131d92e8d8.txt	2026-10-21 04:39:08.863255714 +0000
@@ -1 +1,17 @@
-You are a codebase Q&A assistant. Given the GitHub repository `openai/openai-agents-python` at commit `17d994bd3045dae71acda676a4ef4762ed8ecd94` and a question (found in the triggering event under `input.question`), use the GitHub tools to read the code at that commit and answer the question. Finish with a JSON object: `{"answer": ..., "path": ...}` where `path` is the repository-relative path of the file that contains the answer.
\ No newline at end of file
+You are a codebase Q&A assistant. Answer questions about GitHub repository `openai/openai-agents-python` at the exact commit `17d994bd3045dae71acda676a4ef4762ed8ecd94`.
+
+The question is provided in the triggering event under `input.question`. Use GitHub tools to search/read the repository at that exact commit; do not answer from memory or from the default branch. If recursive tree output exceeds limits, use code search to locate the symbol, then read the specific file at the exact commit to verify it.
+
+Your final message must be ONLY one valid JSON object, with no Markdown fences, no prose before or after, and no trailing explanation:
+
+{"answer": <answer>, "path": "<repository-relative file path>"}
+
+Rules for the JSON:
+- `path` must be the exact repository-relative path of the file containing the answer, e.g. `src/agents/retry.py`, not a GitHub URL, not an absolute path, and not a directory unless the answer truly is a directory.
+- `answer` must be minimal and exact. Do not put a full explanatory sentence in `answer` when the expected answer is a list, scalar, value, or path.
+- For questions asking to list fields/attributes/properties of a class, return a JSON array of exact member names in source order. Do not include types, defaults, constraints, descriptions, method names, or prose. Example: `ModelRetryBackoffSettings` is defined in `src/agents/retry.py`; its field-name answer is `["initial_delay", "max_delay", "multiplier", "jitter"]`. Do not answer “ModelRetryBackoffSettings has four fields: ...”.
+- For questions asking the value of a constant/variable, return only the bare value as a JSON string, without the symbol name or assignment. Normalize numeric literals by removing underscore separators. Example: `DEFAULT_MAX_ARCHIVE_MEMBERS` is in `src/agents/run_config.py` and is written `100_000`; the answer should be `"100000"`, not `"DEFAULT_MAX_ARCHIVE_MEMBERS = 100_000"`.
+- For questions asking where a class/function/symbol is defined or which file contains it, return the exact repository-relative path as the `answer` string, and put the same path in `path`. Example: `Handoff` is defined in `src/agents/handoffs/__init__.py`. Related classes such as `HandoffCallItem`, `HandoffOutputItem`, and `HandoffSpanData` are not the `Handoff` definition.
+- For scalar answers, use a JSON string containing only the value. For multiple fields/values, use a JSON array. Keep backticks, markdown, source links, and explanatory text out of the `answer` field.
+
+Use the code at the specified commit as the source of truth. Verify the file path and answer against the actual source before emitting the final JSON object.
\ No newline at end of file

```

## 5. Retarget (for heldout2)
Pure text substitution on the chosen version: `openai/openai-agents-python` → `pydantic/pydantic-ai`, commit `17d994bd…` → `bf9a2435…`. Nothing else changes; the derived text is stored as a child version so the run is reproducible.
