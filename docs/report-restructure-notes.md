# Page restructure (asked by Yuandong 2026-10-21 ~17:10 UTC)
"更新你的v1 html吧；就直接讲这个bench就行；然后之前的那个放到appendix；先把baseline放进去"
Main storyline = SWE-QA-Pro sub-bench (qa). C1 (old pages 2-4 + old appendix) -> appendix tabs.
New tabs: 1 Pipeline (keep diagram; generic wording, quality=judge) · 2 Bench & prompt (SWE-QA-Pro repos/splits table, qa v0 instruction text from src/hidden_layer/improve/bench/qa/instruction_v0.md, judge prompt summary + checks, metric definitions with quality = judge total/50) · 3 Baseline (charts by split: quality, cost, turns, tool calls, latency; per-question table with question text; GEPA not yet run; budget ~$20 cap max_metric_calls=200) · Appendix A C1 setup · B C1 prompt diff · C C1 results · D C1 data.
Data: /home/ubuntu/Documents/prompts/qa_runs.json (130 runs, v0 001a42091bad; train 10 pilot k=1, val 60, heldout 60).
Baseline: val 0.907 $0.103 11.3 turns 14.2 tools 79s; heldout 0.912 $0.052 7.8 turns 9.4 tools 57s; train 0.876 $0.045. Judge flash; consistency ±1/50; pro not stricter. Spend ≈ $10.4.
Build: /home/ubuntu/Documents/report/build.py -> body.html -> interactive_artifact_compile -> improve-with-ola-v1.html; test: pw/test.js (node). Existing p6 section = V1.5 draft to fold into new tabs.
GEPA budget told to user: ~$20 total (seed val $2, accepted round ~$2.3, rejected ~$0.3, final heldout k=3 $3.5), hard cap max_metric_calls=200 + NoImprovementStopper(8). Not started — wait for his go.
