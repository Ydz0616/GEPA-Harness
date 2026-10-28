# Handout — continue the GEPA experiment in a new session

## TL;DR
Two containers: **pgvector** (Postgres, host :5433, DB `hl_improve`) and **hl** (Hidden Layer from the experiment
branch, API :8080, tenant `devinlive`, memory off). Restore `data/db/` into the DB, connect the GitHub toolkit,
re-run one val question to prove the path works, then start on the TODO list below.
Nothing here needs a new run to *analyze*: all 502 runs, candidate texts, reflector prompts and judge feedback are
already in `data/` and `experiments/`.

## 0. Prerequisites
- Checkout of `SeekMi-Technologies/Hidden_Layer_Internal` on branch `devin/1792547019-improve-s1-mem0-versions`
  (commit `90d8855a`), next to this repo: `../Hidden-Layer-Internal`.
- Secrets (put them in `env/experiment.env`, copied from `env/experiment.env.example`):
  `HL_DEEPSEEK_API_KEY`, `HL_LANGFUSE_PUBLIC_KEY` / `HL_LANGFUSE_SECRET_KEY`, `HL_COMPOSIO_API_KEY`.
- A host venv for the `hl improve` CLI (it talks to the API on :8080 and to the DB on :5433):
  `cd ../Hidden-Layer-Internal && python3.12 -m venv .venv && .venv/bin/pip install -e ".[improve]" -c constraints.txt`

## 1. Start the two containers
```bash
cp env/experiment.env.example env/experiment.env   # fill in
HL_REPO=$(realpath ../Hidden-Layer-Internal) docker compose -f env/docker-compose.yml up -d --build
docker compose -f env/docker-compose.yml ps          # both up; hl runs `hl db-upgrade` then `hl run`
curl -s localhost:8080/healthz                       # HL is serving
```
The hl container already sets `HL_TENANT_ID=devinlive`, `HL_MEMORY_BACKEND=off`, `HL_PUBLIC_URL`,
`HL_MCP_RESULT_MAX_CHARS=400000` (the 50k default discards large GitHub files).

## 2. Restore the experiment data
```bash
../Hidden-Layer-Internal/.venv/bin/python env/restore_db.py
# inserted {'automations': 3, 'automation_instruction_versions': 16, 'improve_runs': 502}
```
Verify — must print v0 `001a42091bad` with 136 finished runs, quality ≈ 0.910, and every candidate:
```bash
export HL_PG_DBNAME=hl_improve HL_TENANT_ID=devinlive HL_MEMORY_BACKEND=off
../Hidden-Layer-Internal/.venv/bin/hl improve report --automation 6550dcc0ce9f
```
Automations: `6550dcc0ce9f` = qa (SWE-QA-Pro), `9c075b7547ec` = C1 (English), `fa7957f21c23` = C1 Chinese (superseded).

## 3. Instance gotchas (each cost time before)
- Billing gate: a fresh instance is on the free plan (20M units) and stops runs with `QuotaExceeded` — raise
  `billing_plan` in the experiment DB.
- Rate cap: restored automations keep `rate_limit = {"max_runs": 1000, "window_minutes": 60}`; a new
  `hl improve setup` automation gets 20/hour — raise it before batch runs or queued tasks are cancelled.
- DeepSeek HTTP 402 "Insufficient Balance" fails runs; the runner marks them `infra_provider` and retries once.
  Top up before long runs. Rows with status `infra_provider` / `infra_timeout` are excluded from scores.
- Tool calls: count from `agent_messages` (`function_call` items), not Langfuse (it undercounts / 429s).

## 4. Connect the GitHub toolkit (Composio)
The org Composio account already holds an ACTIVE GitHub connection for user_id `devinlive`, so no OAuth click:
seed the integration with the existing auth config id (ask Yuandong / Composio dashboard — not published here),
then let HL provision the MCP server:
```bash
docker exec -it gh_hl python -c "from hidden_layer import db, integrations; from hidden_layer.config import Settings; \
integrations.upsert(db.pg_pool(Settings()), 'composio', enabled=False, status='auth_config_created', meta={'auth_config_id': '<AUTH_CONFIG_ID>'})"
docker exec -it gh_hl hl connect --no-browser
```
The tenant slug must not contain `_` (Composio rejects the MCP server name).

## 5. Smoke test — one val question through the real path (~$0.1)
```bash
../Hidden-Layer-Internal/.venv/bin/hl improve run qa --automation 6550dcc0ce9f --version 001a42091bad \
  --only qa-sanic-06 -k 1 -c 1
../Hidden-Layer-Internal/.venv/bin/hl improve report --automation 6550dcc0ce9f   # v0 now 137 runs
```
Pass = status `done`, a judge score, a trace in Langfuse (environment `improve-devinlive`).

## 6. Commands used for the reported runs
```bash
# baseline (v0) on val + heldout, k=3 — resume helper: experiments/qa-baseline/qa_resume.sh
hl improve run qa --automation 6550dcc0ce9f --version 001a42091bad --split val -k 3 -c 3
# GEPA (main run, experiments/qa-gepa/v15-qa-gepa-2)
hl improve optimize qa --automation 6550dcc0ce9f --run-dir <dir> --max-metric-calls 100 \
  --no-improvement 8 --minibatch 3 -k 1 -c 3 --val-per-repo 5 --reuse-seed-runs
# resume = same command, same --run-dir (gepa_state.bin); stop = touch <dir>/gepa.stop
# held-out exam (NOT run yet; needs Yuandong's OK): c2 = 3120b6f2f46c, 20 Qs x k=3 = 60 runs
hl improve run qa --automation 6550dcc0ce9f --version 3120b6f2f46c --split heldout -k 3 -c 3
```

## 7. Open decisions (do not do without Yuandong)
- Run the held-out exam (c2 vs the v0 baseline already in the DB).
- Finish c5 `2efa85c19843` on its 7 missing val questions (does not change "c2 is best").
- Adopt any candidate in production — never automatic.

## 8. Next-session TODO (Yuandong's list) and where to start

| # | question | start from |
|---|---|---|
| 1 | What are the ASI we are giving to GEPA? | `improve/evaluators/qa.py` (feedback text) · `feedback` column in `data/db/improve_runs` · `reflection_calls.jsonl` `<side_info>` |
| 2 | Vertical prompt diffs and how the context is assembled for the GEPA reflector | `automation_instruction_versions` (all texts) · `improve/reflection.py` + `gepa_adapter.make_reflective_dataset` · GEPA `instruction_proposal.py` · `reflection_calls.jsonl` (exact prompts sent) |
| 3 | GEPA: a single prompt that would work for multiple tasks | C1 + qa automations share the harness; c2 is 83% train-repo facts — strip them and re-score (ablation) |
| 4 | Try optimizing the system (not just the instruction) | tool set, result cap, model, turn limit — `metrics_json` / turns / tool calls per run |
| 5 | Would feeding the traces directly to agents help better than GEPA? | Langfuse traces by `trace_id` in `improve_runs`; same val 10 Qs as comparison set |
| 6 | How people have approached the SWE-QA-Pro benchmark | `bench-survey/` notes, SWE-QA-Pro paper (arXiv 2603.16124) and its leaderboard/agents |
| 7 | Look into the traces | `trace_id` → Langfuse (`improve-devinlive`); `agent_messages` for tool calls |
| 8 | More qualitative / quantitative analysis of the prompt | report tabs 4 + Appendix E; per-question deltas; judge-dimension breakdown in `judge-calls.jsonl` |

Done-criterion for each item: a short written finding (with the numbers and the run/trace ids it rests on) added to
`docs/`, and any new run recorded in `improve_runs` + exported with `env/export_db.py`.
