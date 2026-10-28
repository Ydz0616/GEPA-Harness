exec(open("/home/ubuntu/Documents/report/gepa_viz.py").read())
import json as _gj
_G = _gj.load(open("/home/ubuntu/Documents/report/gepa_val.json")); _S = _G["stats"]
_LEN = {"v0": 292, "c1": 6799, "c2": 17854, "c3": 25612, "c4": 14274}
_NAME = {"v0": "v0 <code>001a4209</code>", "c1": "c1 <code>5605704e</code>", "c2": "c2 <code>3120b6f2</code>", "c3": "c3 <code>bcfe503b</code>", "c4": "c4 <code>b2987d58</code>"}
_NOTE = {"v0": "seed · 3 runs/Q (baseline)", "c1": "accepted · parent v0", "c2": "accepted · parent c1 · best accepted", "c3": "parent c2 · kept on Pareto front, below c2 on aggregate", "c4": "parent c1 · below c2"}
def _row(k):
    s = _S[k]
    return (f'<tr><td>{_NAME[k]}</td><td>{_NOTE[k]}</td><td data-numeric>{_LEN[k]:,}</td><td data-numeric>{s["q"]:.3f}</td>'
            f'<td data-numeric>{s["turns"]:.1f}</td><td data-numeric>{s["tools"]:.1f}</td><td data-numeric>${s["cost"]:.3f}</td>'
            f'<td data-numeric>{s["lat"]:.0f}</td><td data-numeric>{s["anslen"]:,}</td></tr>')
_TRAJ = "".join(_row(k) for k in ("v0", "c1", "c2", "c3", "c4")) + '<tr><td>c5 <code>2efa85c1</code></td><td>parent c1 · val not completed: 3/10 questions scored (0.94, 0.90, 0.96) before the model provider stopped serving; excluded</td><td data-numeric>14,808</td><td data-numeric>—</td><td data-numeric>—</td><td data-numeric>—</td><td data-numeric>—</td><td data-numeric>—</td><td data-numeric>—</td></tr>'
def _cell(k, e):
    v = _S[k]["per"].get(e); return f'<td data-numeric>{v:.2f}</td>' if v is not None else '<td data-numeric>…</td>'
_PERQ = "".join(f'<tr><td style="white-space:nowrap">{e}</td>' + "".join(_cell(k, e) for k in ("v0", "c1", "c2", "c3")) + "</tr>" for e in _G["ids"])
_CH = "".join(f'<tr><th scope="row">{k}</th><td data-numeric>{_S[k]["q"]*100:.1f}</td></tr>' for k in ("v0", "c1", "c2", "c3"))
GEPA_SECTION = f"""
<section role="tabpanel" id="p10" aria-labelledby="t10" class="a-section" hidden>
  <h2 class="a-section__title">GEPA on SWE-QA-Pro — search results (held-out pending)</h2>
  <p class="a-section__note">GEPA finished at 22:05 UTC after using its 100-metric-call budget (8 iterations; 5 candidates reached val evaluation; c2 is the final best). Held-out has not been run for any candidate, so nothing here is a generalisation claim yet.</p>
  <h3 class="a-section__title" style="margin-top:16px">Question</h3>
  <p class="a-prose">Can reflective prompt evolution (GEPA), driven only by an LLM judge's scores and feedback on a handful of training runs, improve a production automation instruction — and does the improvement transfer to repositories the optimiser never saw?</p>
  <h3 class="a-section__title" style="margin-top:16px">Setup</h3>
  <dl class="a-meta-list">
    <div><dt>Agent</dt><dd>Hidden Layer automation, unchanged execution path; DeepSeek flash; GitHub toolkit over MCP; the only thing that varies is the instruction text</dd></div>
    <div><dt>Data</dt><dd>SWE-QA-Pro sub-bench: train = pint, responses (reflection sees these); val = 10 Q from sanic + dwave-cloud-client (candidate selection, drawn by seed, blind to scores); held-out = tox, docker-py (20 Q × 3, never used)</dd></div>
    <div><dt>Objective</dt><dd>official SWE-QA-Pro judge, 5 dimensions × 1–10, quality = total / 50; judge feedback (reference answer + per-dimension scores) and an execution trace are the reflection's side information</dd></div>
    <div><dt>Search</dt><dd>GEPA default reflective mutation, per-example Pareto frontier, train minibatch 3, val k=1 per candidate, stop at 100 metric calls or 8 rounds without improvement; seed scored from its existing baseline runs</dd></div>
  </dl>
  <h3 class="a-section__title" style="margin-top:16px">Versions</h3>
  <dl class="a-meta-list">
    <div><dt>v0</dt><dd><strong>Baseline</strong> — the original 292-character instruction; val score = mean of its 3 baseline runs per question</dd></div>
    <div><dt>c1</dt><dd>GEPA candidate 1, rewritten from v0 by one reflection call; accepted</dd></div>
    <div><dt>c2</dt><dd>GEPA candidate 2, rewritten from c1; accepted; <strong>best on val so far</strong></dd></div>
    <div><dt>c3</dt><dd>GEPA candidate 3, rewritten from c2; kept on the Pareto front but below c2 on average</dd></div>
    <div><dt>c4, c5</dt><dd>Two more rewrites of c1. c4 scored 0.914; c5 could not be fully scored (model provider stopped serving after 3 of 10 val questions) and is excluded</dd></div>
  </dl>
  <h3 class="a-section__title" style="margin-top:20px">Result 1 — val quality rises 0.897 → 0.956 (c2); later candidates c3 and c4 do not beat it</h3>
  <details class="a-disclosure"><summary>All numbers per version (table)</summary><div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">Candidates on val</caption>
  <thead><tr><th scope="col">Version</th><th scope="col">Status</th><th scope="col" data-numeric>instr. chars</th><th scope="col" data-numeric>val quality</th><th scope="col" data-numeric>turns</th><th scope="col" data-numeric>tool calls</th><th scope="col" data-numeric>$/run</th><th scope="col" data-numeric>latency s</th><th scope="col" data-numeric>answer chars</th></tr></thead>
  <tbody>{_TRAJ}</tbody></table></div></details>
  <p class="a-section__note">All columns are means over the same 10 val questions. Two further proposals were rejected on their train minibatch and never reached val. One more proposal is excluded because its val runs did not complete (tool-server timeouts), so it has no valid score.</p>
  <div class="a-grid a-grid--halves" style="margin-top:12px">{VIZ_TRAJ}{VIZ_LEN}</div>
  <div class="a-grid a-grid--halves" style="margin-top:12px">{VIZ_SC_COST}{VIZ_SC_TURNS}</div>
  <h3 class="a-section__title" style="margin-top:20px">Result 2 — which questions and which judge scores improved</h3>
  <div class="a-grid a-grid--halves">{VIZ_PERQ}{VIZ_DIMS}</div>
  <details class="a-disclosure"><summary>Per-question quality table</summary><div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">Per-question val quality</caption><thead><tr><th scope="col">Question</th><th scope="col" data-numeric>v0 (mean of 3)</th><th scope="col" data-numeric>c1</th><th scope="col" data-numeric>c2</th><th scope="col" data-numeric>c3</th></tr></thead><tbody>{_PERQ}</tbody></table></div></details>
  <p class="a-section__note">The weakest v0 questions gain most (e.g. dwave-10 0.83 → 0.96, sanic-08 0.85 → 0.90–0.92); questions v0 already answers at ≥ 0.96 stay flat. Consistent with the baseline diagnosis: points were lost on correctness and completeness, not format.</p>
  <h3 class="a-section__title" style="margin-top:20px">Result 3 — what the reflection actually wrote</h3>
  <ul class="a-prose" style="margin:.3em 0 0 1.2em">
    <li><strong>The instruction grows ~60–90×</strong>: 292 → 6.8k → 17.9k → 25.6k characters.</li>
    <li><strong>Two kinds of content.</strong> (a) General answering strategy: pin every read to the commit, trace the call chain from the public entry point for "where" questions, name the exact branch or condition for "why" questions, correct false premises and still answer the intent, open with a direct answer, cite file:line @ commit. (b) Train-repo facts: in c2, ≈ 14.8k of 17.9k characters (83%) are notes about pint and responses internals (file paths, line ranges, call chains).</li>
    <li><strong>No val or held-out repo is ever mentioned</strong> (0 occurrences of sanic, dwave, tox, docker in c3), so the val gain cannot come from leaked answers; it has to come from (a), or from (b) acting as worked examples of the expected depth.</li>
    <li><strong>Answers get longer</strong>: 4.5k → ≈ 7.9k characters on val, with similar turns and tool calls. This is GEPA's default meta-prompt at work: it explicitly asks to "include all niche and domain specific factual information".</li>
  </ul>
  <div class="a-grid a-grid--halves" style="margin-top:12px">{VIZ_COMP}<div></div></div>
  <h4 class="a-section__title" style="margin-top:16px">Prompt diff — v0 → c1 → c2</h4>
{VIZ_DIFF}
  <h3 class="a-section__title" style="margin-top:20px">Example — same question, v0 vs c2 answer</h3>
{VIZ_EX}
  <h3 class="a-section__title" style="margin-top:20px">How much to trust the val gain</h3>
  <div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">Threats to validity</caption><thead><tr><th scope="col">Threat</th><th scope="col">Evidence / size</th><th scope="col">How we address it</th></tr></thead><tbody>
  <tr><td>Selection on val</td><td>val is where GEPA picks winners; the best of several candidates is optimistic</td><td>held-out exam on 2 unseen repos, 20 Q × 3</td></tr>
  <tr><td>Noise</td><td>same question, repeated runs: ±0.04–0.05. Candidates are measured k=1 on 10 Q (SE of the mean ≈ 0.016); seed is a mean of 3. The +0.059 gain is ≈ 3.7 SE, before the selection correction</td><td>held-out at k=3 for both v0 and the chosen candidate</td></tr>
  <tr><td>Judge length bias</td><td>answers ~75% longer; "completeness" may reward length</td><td>re-judge a sample with a length-controlled rubric or a second judge model</td></tr>
  <tr><td>Same model family</td><td>executor, reflector and judge are all DeepSeek flash</td><td>cross-check a sample with a different judge model</td></tr>
  <tr><td>Train-fact bloat</td><td>83% of c2 is pint/responses notes, useless on other repos and a cost in every prompt</td><td>ablation: c2 with the repo-fact section removed, on val and held-out</td></tr>
  <tr><td>Small val</td><td>10 Q from 2 repos</td><td>held-out adds 20 Q from 2 more repos</td></tr>
  </tbody></table></div>
  <h3 class="a-section__title" style="margin-top:20px">Next</h3>
  <ol class="a-prose" style="margin:.3em 0 0 1.2em">
    <li>Let GEPA finish its 100 metric calls; take the best val candidate.</li>
    <li>Held-out exam: candidate on tox + docker-py, 20 Q × 3, against v0's existing 60 held-out runs; report quality with per-question spread plus turns, tool calls, cost, latency.</li>
    <li>Ablation: general rules only (strip repo facts) to separate "strategy" from "worked examples".</li>
    <li>Multi-objective selection (quality vs tool calls / cost) on the logged metrics of all candidates.</li>
  </ol>
</section>
"""
