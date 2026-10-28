# GEPA-Harness

Research record for **Improve with Ola**: optimizing a Hidden Layer (HL) automation instruction with
[GEPA](https://github.com/gepa-ai/gepa), using execution traces + an LLM judge as the signal.

```
instruction version → HL automation run (real execution path) → Langfuse trace + improve_runs ledger
  → evaluator (score + feedback text = GEPA "ASI") → GEPA reflection LM → candidate instruction
  → candidate re-runs on the same path → Pareto selection on val → held-out exam → human adoption
```

The harness code itself lives in the (private) product repo and is **not copied here**:
`SeekMi-Technologies/Hidden_Layer_Internal`, branch `devin/1792547019-improve-s1-mem0-versions`,
commit `90d8855a` (`src/hidden_layer/improve/`: `runner.py`, `gepa_adapter.py`, `reflection.py`, `cli.py`,
`evaluators/{c1,qa}.py`, `ledger.py`, `bench/{c1,qa}/`). This repo holds everything else:
experiment scripts, run artifacts, the DB export, the benchmark survey and the report.

To reproduce or continue: **[HANDOUT.md](HANDOUT.md)** (two containers + next-session TODO).

## Results so far (SWE-QA-Pro sub-bench, scenario `qa`)

Agent and judge: DeepSeek flash. Judge = official SWE-QA-Pro prompt, quality = total/50.
Splits by repository: train `hgrecco/pint`, `getsentry/responses` · val `sanic-org/sanic`,
`dwavesystems/dwave-cloud-client` (GEPA val = 10 Qs, 5 per repo) · heldout `tox-dev/tox`, `docker/docker-py`.

| version | id | parent | instr. chars | val quality | turns | tool calls | $/run | latency s |
|---|---|---|---|---|---|---|---|---|
| v0 (baseline) | `001a42091bad` | – | 292 | 0.897 | 12.3 | 15.3 | 0.107 | 91 |
| c1 | `5605704e4879` | v0 | 6,799 | 0.936 | 13.1 | 16.3 | 0.072 | 118 |
| **c2** | `3120b6f2f46c` | c1 | 17,854 | **0.956** | 11.6 | 16.0 | 0.055 | 124 |
| c3 | `bcfe503b0b1a` | c2 | – | 0.948 | 17.4 | 21.5 | 0.086 | 159 |
| c4 | `b2987d5883ec` | c1 | – | 0.914 | 13.1 | 16.2 | 0.058 | 108 |
| c5 | `2efa85c19843` | c1 | – | *incomplete* (3/10 Qs; provider 402) | | | | |

GEPA stopped at its 100 metric-call budget after 8 iterations. **Not yet a conclusion**:
val is the selection set (optimistic), the held-out exam (c2 vs v0, 20 Qs × k=3) has **not** been run,
and ~83% of c2's text is train-repo-specific knowledge (pint / responses) — needs held-out + ablation.

## Layout

| path | what |
|---|---|
| `HANDOUT.md` | start the two containers, restore data, verify, next-session TODO |
| `env/` | `docker-compose.yml` (pgvector + HL), `experiment.env.example`, `export_db.py`, `restore_db.py` |
| `data/db/` | export of `automations` (no webhook secrets), `automation_instruction_versions` (v0 + every candidate text), `improve_runs` (502 rows: output, score, judge feedback, cost, turns, tool calls, trace id) |
| `data/prompts/` | C1 instruction texts, prompt diff notes, run snapshots used by the report |
| `experiments/c1/` | V1 scenario C1 (deterministic fact QA on `openai-agents-python`): three GEPA run dirs |
| `experiments/qa-baseline/` | v0 baseline stats + resume script; judge call log and judge-consistency check |
| `experiments/qa-gepa/v15-qa-gepa-2/` | **main GEPA run**: `gepa_state.bin` (resumable), `candidates.json`, `run_log.{txt,json}`, `reflection_calls.jsonl` (full reflector prompts + outputs), `judge-calls.jsonl`, `optimize.log`, `candidate_tree.html` |
| `experiments/qa-gepa/v15-qa-gepa-1-aborted/` | first attempt (reflection hit the 4k output cap → empty proposals; fixed in `339f1b82`) |
| `tools/composio-probe/` | Composio GitHub toolkit latency probe + tool schema dump (29 tools) |
| `tools/github-mcp-shim/` | read-only MCP server mimicking Composio's 29 GitHub tools on the GitHub REST API, capture + replay diff vs Composio. Built during the Composio outage; **not used** for any reported run |
| `tools/langfuse/` | backup of per-run tool-call counts pulled from Langfuse |
| `bench-survey/` | notes on SWE-QA, SWE-QA-Pro, RepoQA, CodeRepoQA, Qodo deep_code_bench; sub-bench selection (`stats.py`, `repos.txt`, `subbench_splits.json`); judge script; `pro.jsonl` (SWE-QA-Pro, MIT) |
| `report/` | report generator (`build.py`, `gepa_section.py`, `gepa_viz.py` + json data), final `improve-with-ola-v1.html`, browser test `pw/test.js` |
| `docs/` | `HANDOFF_PROMPT.md` (paste into a new session), experiment log, research scaffold, C1–C3 task cards |

Scripts keep the absolute paths of the original VM (`/home/ubuntu/improve-runs/...` → `experiments/` and `tools/`,
`/home/ubuntu/Documents/report` → `report/`, `/home/ubuntu/bench-survey` → `bench-survey/`). Adjust before re-running.

## Key references
- GEPA reflection meta-prompt: `gepa/src/gepa/strategies/instruction_proposal.py` (default, used verbatim); what fills
  `<curr_param>` / `<side_info>` is in the report's Appendix E and in `reflection_calls.jsonl`.
- SWE-QA-Pro: https://huggingface.co/datasets/TIGER-Lab/SWE-QA-Pro-Bench (arXiv 2603.16124).
