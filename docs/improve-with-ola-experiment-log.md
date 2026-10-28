# Improve with Ola — Experiment Log

> Living document. One section per run; only final decisions are kept. Companion to the plan
> (`improve-with-ola-scaffold.md`) and task cards (`gepa-c1/c2/c3-task-card.md`).
> Last updated 2026-10-21 08:50 UTC (V1 complete; V1.5 baseline complete on SWE-QA-Pro sub-bench: v0 ≈ 0.91).

## 0. Setup (fixed for all runs unless a run says otherwise)

| Item | Value |
|---|---|
| Harness | Hidden Layer, branch `devin/1792547019-improve-s1-mem0-versions` (commits `a17a8a0d`, `1b52a1f8` + English bench) |
| Instance | Devin VM, `hl run` :8080, DB `hl_improve` (pgvector docker, alembic head `b7e1c4d2a9f3`), tenant `devinlive` |
| Memory | `HL_MEMORY_BACKEND=off` (`NullLongTerm`: no recall, no writes) |
| Execution model | `deepseek-flash` (DeepSeek V4 flash) for the agent; reflection (V1+) also DeepSeek, as an HL task with no tools |
| Tools available to the run | GitHub via Composio MCP (read-only toolkit, 29 tools incl. `GITHUB_GET_REPOSITORY_CONTENT`, `GITHUB_SEARCH_CODE`, `GITHUB_GET_A_TREE`), Python sandbox, web search; toolkit must be loaded by the agent (`load_toolkit`) |
| Trigger path | `POST /api/automations/{id}/run` with `instruction_version_id` + `input` → `automation_fire.fire` → `Dispatcher.enqueue` → worker (same path as the console Run button) |
| Trace | Langfuse (`us.cloud.langfuse.com`, environment `improve-devinlive`) |
| Ledger | `improve_runs` (one row per version × example × repeat) |

### Scenario C1 — frozen-repo fact QA
- Repo `openai/openai-agents-python` @ `17d994bd3045dae71acda676a4ef4762ed8ecd94` (tag v0.24.0), questions restricted to `src/agents/`.
- 20 examples (`improve/bench/c1/examples.jsonl`): train 8 / val 6 / heldout 6 (heldout holds the cross-file / count questions). Question types: default value 10, locate-file 5, inheritance 2, call chain 1, field set 1, count 1, cross-file 1.
- The question is delivered to the run as the event payload (`input.question`, also `context`).

### Evaluator (deterministic, no LLM) — `improve/evaluators/c1.py`
1. Take the **last** JSON object in the final reply that has an `answer` member. None → score 0, feedback "no JSON object with an `answer` member".
2. `answer` must equal the gold after normalization: strip whitespace/quotes/backticks, lowercase, drop trailing period, digit separators (`100_000`→`100000`), `1 GiB`/`2**30`→`1073741824`, `None`/`null` equivalent. Set questions (c1-17) compare as sets.
3. `path` must be one of the accepted paths (c1-19 accepts any of the 6 referencing files; c1-16 accepts `__init__.py` or `_config.py`).
4. score = 1 iff answer **and** path match; anything else (incl. failed/timeout runs) = 0.
5. Feedback (the GEPA "ASI" text handed to the reflection LM): question, gold answer, accepted paths, the agent's answer and path verbatim, verdict (which part mismatched). No diagnosis — that is the reflection LM's job.

### Metrics recorded per run (all five from S1 on; only `quality` is optimized in V1)
| Metric | Source |
|---|---|
| quality | evaluator score (0/1) |
| cost_usd | `usage_events_local.cost_usd` of the task_run trace (write-time pricing) |
| latency_s | `tasks.finished − tasks.started` |
| turns | number of LLM requests in the task_run usage receipts |
| tool_calls | Langfuse observations of kind `TOOL` under the trace |

Aggregates: quality mean; pass^k (share of examples correct in all k repeats); cost mean/total; latency median/p90; turns and tool calls mean/p90.

## Run 0 — baseline, v0 instruction in Chinese (superseded; kept for the record)
2026-10-21 02:02–02:25 UTC · automation `fa7957f21c23` · version `7b2d102f3d8e` · 20 × k=3 · concurrency 3 · rows deleted after Run 1 was started (language decision).

| quality | pass^3 | cost mean / total | latency med / p90 | turns mean / p90 | tool calls mean / p90 |
|---|---|---|---|---|---|
| 0.30 (18/60) | 0.10 | $0.021 / $1.26 | 14 s / 59 s | 6.2 / 9 | 6.1 / 10 |

Failure modes: 42 × answer not a bare value (fact right, explanation written into `answer`; paths right) · 3 × genuinely wrong (c1-06 `CURRENT_SCHEMA_VERSION` answered 1.20/1.20/1.19 vs gold 1.21 — the agent read a different revision; also the most expensive example: $0.13, 27 turns, 31 tool calls) · 1 × no JSON. Observation: files >50k chars are discarded by the harness (`remote_mcp._cap_result`), so `run.py` is unreadable and the agent must search instead.

Decision after Run 0 (Yuandong): everything in English (instruction, questions, feedback, report); evaluator stays strict (bare-value match is part of what the instruction must learn); GEPA stop = large `max_metric_calls` + `run_dir` `gepa.stop` file + `NoImprovementStopper`.

## Run 1 — baseline, v0 instruction in English
Started 2026-10-21 02:39 UTC · automation `9c075b7547ec` · version `0d6e62afe17a` (label `baseline`) · 20 × k=3 · concurrency 3.

v0 instruction:
> You are a codebase Q&A assistant. Given the GitHub repository `openai/openai-agents-python` at commit `17d994bd3045dae71acda676a4ef4762ed8ecd94` and a question (found in the triggering event under `input.question`), use the GitHub tools to read the code at that commit and answer the question. Finish with a JSON object: `{"answer": ..., "path": ...}` where `path` is the repository-relative path of the file that contains the answer.

Finished 02:53 UTC (14 min wall, 60 runs, concurrency 3).

| quality | pass^3 | cost mean / total | latency med / p90 | turns mean / p90 | tool calls mean / p90 |
|---|---|---|---|---|---|
| **0.75** (45/60) | 0.55 (11/20 examples correct 3/3) | $0.022 / $1.29 | 15 s / 52 s | 6.4 / 9 | 5.4 / 9 |

Failure modes (15 wrong runs, all `answer` mismatches, every `path` correct):
- 14 × fact correct but `answer` carries an explanation — `"1073741824 bytes (1024 * 1024 * 1024 = 1 GiB)"` (c1-03 ×3), `"None (no limit: …)"` (c1-05 ×3), `"100_000 (i.e. 100,000)"`, `"RunContextWrapper (specifically …)"`, the field list written as prose (c1-17 ×2).
- 1 × genuinely wrong: c1-06 `CURRENT_SCHEMA_VERSION` → 1.20 once (gold 1.21); the agent did not read the pinned commit. Still the most expensive example ($0.14, 29 turns, 32 tool calls, 208 s).

Per-example quality (k=3): c1-01/08/11–16/18–20 = 1.00 · c1-02/04/06/07/09 = 0.67 · c1-10/17 = 0.33 · c1-03/05 = 0.00.

Read: switching the instruction to English alone moved quality 0.30 → 0.75 — the Chinese v0 made the model explain inside `answer`. What is left for the optimizer is (a) the output contract (bare value, set as a list) and (b) actually reading the pinned revision (c1-06). This is the V1 target; baseline is well below the 90% ceiling.

Split baselines (k=3): train (8) 0.75 · val (6) 0.67 · heldout (6) 0.83.

## V1 — GEPA, quality only (C1)
Started 2026-10-21 02:55 UTC · seed version `0d6e62afe17a` · train 8 (reflection minibatch 3) / val 6 (Pareto frontier) / heldout 6 untouched · k=1 inside GEPA · reflection LM = `deepseek-flash` via the commander's binding, no tools.
Stop: `max_metric_calls=400` (≈ 50 full val passes) · `gepa.stop` file in the run dir · `NoImprovementStopper(8)`.
Run dir `/home/ubuntu/improve-runs/v1-c1-b` (GEPA state, `reflection_calls.jsonl`, `summary.json`).

- **V1a (02:55–03:01, aborted by the no-improvement stopper):** adapter bug — `HLAdapter` did not declare GEPA's optional `propose_new_texts` protocol attribute, so every reflection step raised `AttributeError` and GEPA re-evaluated the seed for 8 iterations without ever proposing a candidate. 27 extra seed runs ($0.13) and no reflection calls. Fixed (`propose_new_texts = None`, commit on the branch) and relaunched as V1b at 03:01 UTC with identical settings and a fresh run dir.

- **V1b (03:01–03:07, aborted by the no-improvement stopper):** the DeepSeek API account ran out of credit at 02:56:43 UTC (`402 Insufficient Balance`) — every agent run and every reflection call after that failed; GEPA saw 0.0 everywhere and stopped after 8 iterations. The Run 1 baseline finished at 02:53 and is unaffected. Failed rows removed from `improve_runs`. V1 relaunches unchanged once the account is topped up.

- **V1c:** relaunched after the account was topped up, identical settings, run dir `/home/ubuntu/improve-runs/v1-c1-c`.

Results (V1c, 03:14–03:22 UTC):
- Iteration 1: reflection (1 call, 1705 in / 3161 out tokens, $0.0043, 16 s) proposed candidate **`0b131d92e8d8`** (2646 chars vs 434 for v0). Minibatch 3/3 → accepted; val 6/6 = **1.00** (k=1; seed scored 0.56 on the same val pass). Candidate text saved at `v1-c1-c/candidate_0b131d92e8d8.md`.
- Iteration 2+: GEPA selected the candidate, found every subsample already perfect and proposed nothing (there is nothing left to learn from val at k=1). Stopped by hand (`gepa.stop`) at 03:22 to spend the budget on validation instead of idle iterations.
- Metric calls: 9 seed + 15 candidate = 24 runs; optimizer overhead = 1 reflection call ($0.004).

What the candidate adds (diff vs v0, in substance): answer ONLY with a JSON object (no fences, no prose); `answer` must be the minimal exact value (scalar / path / list as a JSON array); `path` repository-relative; read at the exact commit, never from memory or the default branch; if the tree is too large use code search then read the file at the commit. All four points map to the Run 1 failure modes.

Validation (started 03:23 UTC, k=3, same instance): heldout 6, val 6, train 8 with the candidate → compare with Run 1 per split (train 0.75 / val 0.67 / heldout 0.83). Heldout (18 runs, done 03:31): **0.78** (14/18) vs Run 1 heldout 0.83 — not better. Cost $0.037/run (Run 1: $0.022), turns 9.6, tool calls 9.7, latency 59 s: the longer instruction makes the agent more thorough and more expensive. Wrong runs: c1-06 ×2 (answered 1.20 / 1.18 — still not the pinned revision) and c1-19 ×2 (`path` = `src/agents`, a directory, for the cross-file count question).

Why c1-06 keeps failing (trace `b5abe062…`): the agent does call `GITHUB_GET_A_TREE` at the pinned sha, but `run_state.py` is above the harness's 50k-char tool-result cap, so it cannot read the file at that commit; it falls back to `GITHUB_SEARCH_CODE`, which only indexes the default branch, and even probes versions by searching `CURRENT_SCHEMA_VERSION 1.16/1.10/1.21/1.20` — then guesses. This is an environment limit (no ranged/partial file read at a ref), not something the instruction can fix. Candidate for the backlog: a line-range read tool or a higher cap.

### V1 result — candidate `0b131d92e8d8` vs baseline v0, k=3 (03:23–03:39 UTC)

| split | quality v0 → cand | cost/run v0 → cand | turns v0 → cand | tool calls v0 → cand |
|---|---|---|---|---|
| train (8) | 0.75 → **1.00** | $0.014 → $0.013 | 5.1 → 4.7 | 4.0 → 2.8 |
| val (6) | 0.67 → **1.00** | $0.012 → $0.011 | 4.8 → 4.2 | 3.2 → 2.4 |
| heldout (6) | 0.83 → 0.78 (15/18 → 14/18) | $0.042 → $0.037 | 9.9 → 9.6 | 9.4 → 9.7 |
| all 20 | 0.75 → **0.93** (45/60 → 56/60) | $0.022 → $0.019 | 6.4 → 6.0 | 5.4 → 4.8 |

Verdict:
- The loop works end to end: one reflection ($0.004) turned the four Run 1 failure modes into instruction rules; every in-distribution example is now 3/3 and cost / turns / tool calls did not go up (slightly down).
- The V1 done-criterion ("heldout > baseline beyond k=3 noise") is **not met**: 14/18 vs 15/18 is one run. The 4 heldout misses are two examples the instruction cannot fix — c1-06 (file above the 50k tool-result cap at the pinned ref; code search only indexes the default branch) and c1-19 (`path` returned as the directory for a cross-file count; a contract ambiguity in the question/evaluator rather than a reading error).
- Optimizer overhead for V1c: 1 reflection call + 24 metric runs ≈ $0.45; validation 60 runs ≈ $1.15.

Next (for decision): (a) remove the environment limit — a line-range / chunked file read at a ref, or raise the cap — and re-run c1-06; tighten the c1-19 contract (ask for one referencing file explicitly). (b) Run the planned second-repo heldout (pydantic-ai, 10 same-type questions) so heldout is a distribution shift, not 6 questions dominated by two environment-bound ones. (c) Then V2 (hold quality, optimize tool calls or cost).



## V1 follow-up A — environment limit lifted (03:49 UTC)
Decision (Yuandong): lift the limit, then do the planned second-repo heldout; one task at a time.
- `HL_MCP_RESULT_MAX_CHARS` (new setting, default 50k unchanged; `remote_mcp._cap_result` reads it) set to 400k on the experiment instance; c1-19 reworded to ask for the count as `answer` and ONE referencing file as `path`.
- Re-run of c1-06 + c1-19, k=3: **v0 now 3/3 on c1-06** (reads `run_state.py` at the pinned sha: 4 turns, 2 tool calls, $0.066/run — the whole file goes into context) and 3/3 on c1-19. Candidate `0b131d92e8d8` re-run: **6/6** as well (c1-06 $0.067/run, 4–5 turns, 2–3 tool calls). The two heldout misses were environment/contract, not instruction; with them fixed the candidate is 60/60 across all 20 questions vs v0 51/60.
- Incident: the instance's built-in billing gate (`free` plan, 20M billed units/period) ran out at 03:52 UTC — 6 runs failed with `QuotaExceeded` (deleted from `improve_runs`); plan set to `experiment` / 2B units for the experiment DB. Not a model/provider issue.

## V1 follow-up B — second-repo heldout (`heldout2`, distribution shift)
`pydantic/pydantic-ai` @ `bf9a2435…` (v2.9.1), scope `pydantic_ai_slim/pydantic_ai/`, 10 questions of the same types (gold checked against the checkout). Both v0 and the candidate are run with the repo slug + commit substituted (`--retarget`), k=3.
- v0 (retargeted `2601174f8e38`): **25/30 = 0.83**. Misses h2-04 ×2, h2-06 ×2, h2-08 ×1 — all the Run-1 failure mode (prose/markdown around the JSON, explanation inside `answer`), no factual errors.
- candidate (retargeted `fbfaee688b85`): first attempt lost 28 runs to a DeepSeek `402 Insufficient Balance` (04:02 UTC, rows deleted); re-run after top-up (04:16–04:31 UTC): **30/30 = 1.00** (32/32 including the two runs that completed before the 402).

| heldout2 (pydantic-ai, 10 Qs, k=3) | v0 | candidate |
|---|---|---|
| quality | 25/30 = 0.83 | **30/30 = 1.00** |
| cost / run | $0.022 | $0.014 |
| latency median / p90 | 16.5 s / 44 s | 13 s / 27 s |
| turns mean | 4.7 | 4.5 |
| tool calls mean | 3.2 | 2.5 |
| run cost | $0.65 | $0.44 |

## V1 conclusion (04:35 UTC)

- **V1 criterion met.** The candidate produced by one GEPA reflection (DeepSeek, $0.004) beats v0 on a repo it never saw: 0.83 → 1.00 on heldout2 (5 v0 misses, all output-contract errors, all fixed), with lower cost, turns, tool calls and latency as side effects — none of these were in the objective.
- In-distribution (first repo, env cap lifted): v0 51/60 → candidate 60/60.
- What was learned is procedural (strict JSON output, bare-value answers, repo-relative paths, read at the pinned commit; code search before tree when the tree is large) — exactly the four Run-1 failure modes, and exactly the kind of knowledge GEPA's reflective prompt asks for. It is not a gain in reasoning.
- Caveats: the benchmark is easy enough that val saturated after one round (GEPA had nothing left to propose); heldout2 has 10 questions; k=3 noise on 30 runs is roughly ±1–2 correct. Harder/larger val is the first thing to fix before V2.
- Total spend today: ~275 valid runs ≈ $5.7 (ledger) + Run 0 $1.26; two provider/quota outages cost ~60 failed runs.

### Next (not started)
- V2: hold quality, optimise a second dimension (tool calls preferred — deterministic); needs an acceptance rule (`quality − λ·x` or custom `acceptance_criterion`) since GEPA accepts on the primary score only.
- H: C2 (reconciliation) and C3 (activity report) through the same runner/adapter.

## Artifacts
- Demo page (self-contained HTML, 4 pages + appendix): `/home/ubuntu/Documents/report/improve-with-ola-v1.html` (built by `report/build.py` from `prompts/runs.json`).
- Prompts, reflection records and v0→candidate diff: `/home/ubuntu/Documents/prompts/prompts-and-diff.md`.

## Correction — tool-call counts (06:50 UTC)
Tool calls were first counted as Langfuse TOOL spans. The runner stopped polling as soon as any TOOL span appeared, and Langfuse ingestion lags the end of a task, so that count undercounted (mean −1.2 calls/run; equal in 68 of 193 runs; never over). All 232 completed runs were recounted from the run's own transcript (`agent_messages` items of type `function_call`); the runner now uses that source. The Langfuse API key of the instance also started returning 401 during the session. Corrected tool calls/run (latest k=3), v0 → candidate: train 4.96 → 4.13, val 4.39 → 3.56, held-out 4.44 → 4.72, held-out 2 4.40 → 4.07. Earlier tables in this log that quote tool calls use the old count. Quality, cost, latency and turns are unaffected.

## V1.5 — harder bench: SWE-QA-Pro sub-bench (`qa`), baseline only

**Why.** C1 was too easy: v0's misses were all output-format, and GEPA saturated val after one round. V1.5 uses a published benchmark instead of hand-written questions.

**Bench.** SWE-QA-Pro Bench (TIGER-Lab, MIT; 260 Q over 26 long-tail Python repos, each pinned to a commit, filtered to need repository exploration). Sub-bench: 6 repos × 10 Q drawn at random (seed 20261021) from the ten smallest repos, split by repository — train `hgrecco/pint`, `getsentry/responses`; val `sanic-org/sanic`, `dwavesystems/dwave-cloud-client`; heldout `tox-dev/tox`, `docker/docker-py`. The instruction is repo-agnostic; repo + commit arrive in the triggering event.

**Scoring.** The benchmark's own judge prompt, verbatim: five 1–10 scores (correctness, completeness, relevance, clarity, reasoning), total 5–50; GEPA score = total / 50. Judge = DeepSeek flash, temperature 0, through the Hidden Layer binding (the benchmark's `--judge deepseek` uses `deepseek-chat`, temperature 0).

**Judge checks (pilot, 10 train Q).** Reference answer as candidate → 50/50 ×3; first third of the reference → 32–33; a wrong one-liner → 6–12. Same answer judged 3× → stdev ≈ 1 point (of 50). DeepSeek v4-pro as judge was not stricter (42.4 vs 43.8 mean) and costs 3.5×, so flash stays.

**Baseline v0 (`001a42091bad`).**

| split | runs | quality | per-Q spread | $/run | turns | tool calls | latency median |
|---|---|---|---|---|---|---|---|
| train (pilot, k=1) | 10 | 0.876 | — | $0.045 | 6.5 | 8.0 | 43 s |
| val | 60 | **0.907** | ±0.05 | $0.103 | 11.3 | 14.2 | 79 s |
| heldout | 60 | **0.912** | ±0.04 | $0.052 | 7.8 | 9.4 | 57 s |

Questions averaging < 0.8: val `qa-dwave-cloud-client-03` (0.79); heldout `qa-tox-05` (0.67), `qa-docker-py-10` (0.75). Judge dimensions: relevance/clarity ≈ 9–9.5, correctness/completeness ≈ 7.7–7.9 — lost points are thoroughness, not format.

**Incidents.** (1) A new automation gets Hidden Layer's default rate cap of 20 runs/60 min; runs 21+ were cancelled before any model call (110 rows, no spend). Cap raised to 1000/60 min. (2) DeepSeek balance ran out twice (07:22, 08:41 UTC); failed rows removed, completed runs kept; the last 23 runs were completed after a top-up (16:40–17:00 UTC).

**Spend.** ≈ $10.4 on qa (runs $9.8 + judge $0.58). Larger repos cost more than the pilot predicted ($0.11/run on val vs $0.045 in the pilot).

**Read.** v0 ≈ 0.91 on both val and heldout, with low run-to-run spread. There is headroom of a few points (thoroughness), measurable at this noise level, but small. Decision pending: run GEPA on this bench (expect ~0.91 → ~0.95 at best), or pick harder repos where v0 scores lower.
