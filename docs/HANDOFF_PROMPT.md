# Handoff prompt — Improve with Ola / GEPA (paste into a new Devin session)

## TL;DR
You are continuing a research experiment: GEPA optimizes a Hidden Layer (HL) automation instruction using
execution traces + an LLM judge. On a 10-question val subset of a SWE-QA-Pro sub-bench, the best candidate
**c2 (`3120b6f2f46c`) scores 0.956 vs the v0 baseline 0.897**. This is **not yet a result**: val is the selection set,
the held-out exam has not been run, and ~83% of c2's text is train-repo-specific knowledge.
Your job this session is the **analysis / research TODO list in Stage 1–3 below**, not new product features.
Everything you need is in `https://github.com/Ydz0616/GEPA-Harness` (read `README.md` and `HANDOUT.md` first).

## Working rules (from Yuandong)
- Reply in Chinese, short and plain; research artifacts may be in English. Explain any jargon you use.
- Work in stages. Announce each stage (what + which TODO), report when it is done, then **wait for his OK before
  the next stage**. When he asks a question, answer it; don't start changing code.
- Research framing: question → setup → method → result → how much to trust it → next step. No ops/incident or
  budget narrative in reports. Visualize results (charts), don't hand over tables only.
- **Never without his explicit OK**: run the held-out exam; spend on new GEPA runs; adopt any candidate in production.
- Don't over-verify; don't web-search other tools — read their source repos directly (e.g. GEPA's repo).
- Public repo: never commit keys, Composio auth config ids, webhook secrets, or HL product source.

## Where things are
- **Research repo** (public, you can push to `main`): `Ydz0616/GEPA-Harness`
  - `HANDOUT.md`: two containers (pgvector :5433 + HL :8080), restore, connect GitHub toolkit, smoke test, commands
  - `data/db/*.jsonl.gz`: `improve_runs` (502 rows: answer, score, judge feedback, cost, turns, tool calls,
    `trace_id`), `automation_instruction_versions` (v0 + every candidate's full text), `automations`
  - `experiments/qa-gepa/v15-qa-gepa-2/`: main GEPA run — `reflection_calls.jsonl` (exact reflector prompts and
    outputs), `judge-calls.jsonl`, `run_log.json` (per-iteration minibatch ids/scores), `candidates.json`,
    `gepa_state.bin` (resumable)
  - `report/improve-with-ola-v1.html`: the report presented to the PhD (tab 4 = GEPA; Appendix E = judge prompt and
    GEPA reflection meta-prompt)
  - `docs/improve-with-ola-experiment-log.md`: full history of runs, decisions and failures
- **Harness code** (private): `SeekMi-Technologies/Hidden_Layer_Internal`, branch
  `devin/1792547019-improve-s1-mem0-versions`, commit `90d8855a`, under `src/hidden_layer/improve/`
  (`runner.py`, `gepa_adapter.py`, `reflection.py`, `cli.py`, `evaluators/qa.py`, `evaluators/c1.py`, `ledger.py`,
  `bench/qa/`). PR #941 to main was closed by Yuandong; the branch is the record. Read the repo's `AGENTS.md` before
  touching product code.
- GEPA source: `https://github.com/gepa-ai/gepa` — default reflection meta-prompt in
  `src/gepa/strategies/instruction_proposal.py`.

## Final decisions so far
- Benchmark: SWE-QA-Pro (TIGER-Lab, MIT) sub-bench, 6 repos × 10 Qs, split by repository: train `hgrecco/pint`,
  `getsentry/responses`; val `sanic-org/sanic`, `dwavesystems/dwave-cloud-client` (GEPA uses 5 per repo = 10);
  heldout `tox-dev/tox`, `docker/docker-py`.
- Judge: the benchmark's verbatim prompt, DeepSeek flash, temperature 0; inputs = question, reference answer,
  extracted final answer; quality = total of five 1–10 scores / 50. Judge consistency ±1/50; v4-pro not stricter.
- Agent and reflection model: DeepSeek flash. Memory off (`HL_MEMORY_BACKEND=off`). GitHub toolkit = Composio MCP
  (29 read-only tools). Stay on Composio; the Composio-mimicking MCP in `tools/github-mcp-shim` is unused backup.
- GEPA config: max 100 metric calls, minibatch 3, k=1, no-improvement stop 8, seed reuses baseline runs.
  Reflection output budget 32k; empty proposals fail loudly. Runs that don't finish are retried once, never scored 0;
  rows `infra_provider` / `infra_timeout` are excluded.
- Candidates (val): v0 `001a42091bad` 0.897 → c1 `5605704e4879` 0.936 → **c2 `3120b6f2f46c` 0.956**;
  c3 `bcfe503b0b1a` 0.948 (child of c2); c4 `b2987d5883ec` 0.914 (child of c1); c5 `2efa85c19843` incomplete
  (3/10 Qs, DeepSeek 402) — not a score.
- Known caveats to carry into every write-up: val selection bias; ~3.7 SE gain on 10 Qs; judge may prefer longer
  answers (answer length 4.5k → 7.9k chars); same model family for agent/judge/reflector; c2 accumulates train-repo
  facts; dwave-10's apparent gain is mostly one bad v0 run (0.52/0.96/1.0).
- Pending decisions for Yuandong: held-out exam (c2, 20 Qs × k=3 = 60 runs); finishing c5's 7 missing val Qs.
  Top up DeepSeek before any run (402 recurs).

## Stages

### Stage 0 — environment (no model spend except the smoke run)
Follow `HANDOUT.md` §0–5: start the two containers, restore `data/db`, connect the GitHub toolkit (ask Yuandong for
the Composio auth config id), run one val question.
Done when: `hl improve report --automation 6550dcc0ce9f` shows v0 with 136 restored runs + 1 new `done` run with a
judge score and a Langfuse trace. Report and wait.

### Stage 1 — what GEPA actually sees and writes (offline, from existing data; TODO 1, 2, 7, 8)
1. **ASI given to GEPA**: from `evaluators/qa.py` and `gepa_adapter.make_reflective_dataset`, document exactly what
   per-example feedback (ASI) is built: fields, order, truncation, whether judge reasoning / trace / tool calls are
   included. Show 2–3 real examples from `reflection_calls.jsonl`.
2. **Reflector context assembly**: reconstruct one full reflector call end to end (meta-prompt + `<curr_param>` +
   `<side_info>` for its 3 minibatch examples), with sizes in tokens per part.
3. **Vertical prompt diffs**: v0 → c1 → c2 → c3 (and c1 → c4, c1 → c5) as a lineage view: which sections were added,
   rewritten or dropped per step, classified as general strategy vs train-repo knowledge.
4. **Trace inspection**: for the questions where c2 beats v0 on every run (sanic-06, sanic-09, dwave-01) and one where
   it doesn't, compare v0 vs c2 traces (tool sequence, files read, turns) via `trace_id` / `agent_messages`.
5. **Prompt analysis, qualitative + quantitative**: which instruction rules show up in behavior; score vs answer
   length; per-judge-dimension deltas; cost/turn changes.
Done when: one HTML/markdown write-up in `docs/` (committed) with the numbers and run/trace ids each claim rests on.
Report and wait.

### Stage 2 — literature (no spend; TODO 6)
How others approach SWE-QA-Pro: the paper (arXiv 2603.16124), its released agents/baselines and leaderboard, and
related work in `bench-survey/`. Read source repos, not blog posts.
Done when: `docs/swe-qa-pro-approaches.md` — what agents/scaffolds/models score what, and which ideas transfer to us.
Report and wait.

### Stage 3 — experiment designs (each needs Yuandong's OK + budget before running; TODO 3, 4, 5)
Write a one-page design per item (hypothesis, arms, data, metric, cost estimate, what result would change our
mind), then wait:
- **Single prompt for multiple tasks**: one instruction across C1 + qa (and more repos); incl. an ablation of c2 with
  the train-repo knowledge stripped.
- **Optimize the system, not only the instruction**: tool set, MCP result cap, model, turn limit, as GEPA components
  or a grid.
- **Traces directly to the agent vs GEPA**: e.g. give the agent the relevant past traces/feedback at run time vs a
  GEPA-optimized instruction, on the same val 10 Qs.
- The held-out exam (c2 vs v0) belongs here too if Yuandong approves it.
Done when: designs committed under `docs/designs/` and Yuandong has chosen what to run.

## First message to send Yuandong
A 3–5 line status in Chinese: environment up or not (Stage 0 result), and the Stage 1 plan you're about to start.
Then wait for his OK.
