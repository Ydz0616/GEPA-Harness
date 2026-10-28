import json, collections, statistics as st, difflib, html, re, pathlib
P = pathlib.Path("/home/ubuntu/Documents/prompts"); OUT = pathlib.Path("/home/ubuntu/Documents/report/body.html")
runs = json.load(open(P / "runs.json"))
V = {'0d6e62afe17a': 'v0', '0b131d92e8d8': 'cand', '2601174f8e38': 'v0', 'fbfaee688b85': 'cand'}
SPLITS = [('train', 'Train (8 Q)', 'repo 1'), ('val', 'Val (6 Q)', 'repo 1'), ('heldout', 'Held-out (6 Q)', 'repo 1'), ('heldout2', 'Held-out 2 (10 Q)', 'repo 2')]
agg = collections.defaultdict(lambda: collections.defaultdict(list))
for o in runs:
    a = agg[(o['split'], V[o['v']])]; a['s'].append(o['score'])
    for k in ('cost_usd', 'turns', 'tool_calls', 'latency_s'):
        if o[k] is not None: a[k].append(o[k])
def A(split, v):
    a = agg[(split, v)]; n = len(a['s']); ok = int(sum(a['s']))
    return dict(n=n, ok=ok, q=ok / n, cost=st.mean(a['cost_usd']), turns=st.mean(a['turns']),
                tools=st.mean(a['tool_calls']) if a['tool_calls'] else float('nan'), ntools=len(a['tool_calls']),
                lat=st.median(a['latency_s']), lat90=sorted(a['latency_s'])[max(0, round(0.9 * len(a['latency_s'])) - 1)])
R = {(s, v): A(s, v) for s, _, _ in SPLITS for v in ('v0', 'cand')}
tot = {v: dict(n=sum(R[(s, v)]['n'] for s, _, _ in SPLITS), ok=sum(R[(s, v)]['ok'] for s, _, _ in SPLITS)) for v in ('v0', 'cand')}
r1 = {v: dict(n=sum(R[(s, v)]['n'] for s in ('train', 'val', 'heldout')), ok=sum(R[(s, v)]['ok'] for s in ('train', 'val', 'heldout'))) for v in ('v0', 'cand')}
pq = collections.defaultdict(lambda: [0, 0])
for o in runs: pq[(o['split'], o['ex'], V[o['v']])][0] += int(o['score']); pq[(o['split'], o['ex'], V[o['v']])][1] += 1
exs = sorted({(o['split'], o['ex']) for o in runs}, key=lambda t: (['train', 'val', 'heldout', 'heldout2'].index(t[0]), t[1]))
E = html.escape
v0 = (P / "0d6e62afe17a.txt").read_text().strip(); cand = (P / "0b131d92e8d8.txt").read_text().strip()

def sents(t):
    out = []
    for li, line in enumerate(t.split("\n")):
        if not line.strip(): continue
        for x in re.split(r'(?<=[.:;])\s+(?=[A-Z`{\-])', line):
            if x: out.append((li, x))
    return out
L, Rr = sents(v0), sents(cand)
sm = difflib.SequenceMatcher(a=[x for _, x in L], b=[x for _, x in Rr], autojunk=False)
right = []
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    for li, x in Rr[j1:j2]:
        right.append((li, E(x) if tag == 'equal' else f'<ins>{E(x)}</ins>'))
def para(items):
    groups = collections.OrderedDict()
    for li, x in items: groups.setdefault(li, []).append(x)
    return "".join(f"<p>{' '.join(xs)}</p>" for xs in groups.values())
diff_left, diff_right = para([(li, E(x)) for li, x in L]), para(right)
n_new = sum(1 for _, x in right if x.startswith('<ins>'))

def pct(x): return f"{x*100:.0f}%"
def chart(id_, title, unit, key, fmt, note=""):
    import math
    def cell(x): return f"<td data-numeric>{fmt(x)}</td>" if not (isinstance(x, float) and math.isnan(x)) else "<td data-numeric data-value=\"0\">n/a</td>"
    rows = "".join(f"<tr><th scope=\"row\">{lab}</th>{cell(R[(s,'v0')][key])}{cell(R[(s,'cand')][key])}</tr>" for s, lab, _ in SPLITS)
    return f"""<figure class="a-panel" id="{id_}" data-a-chart="bar" data-a-chart-unit="{unit}" data-a-chart-height="240">
  <figcaption class="a-panel__title">{title}</figcaption>
  <div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">{title}</caption>
  <thead><tr><th scope="col">Split</th><th scope="col" data-numeric>v0 (baseline)</th><th scope="col" data-numeric>Candidate (GEPA)</th></tr></thead>
  <tbody>{rows}</tbody></table></div>{f'<p class="a-section__note">{note}</p>' if note else ''}</figure>"""

def node(x, y, w, h, title, sub, detail, cls=""):
    return f"""<g class="a-node {cls}" data-a-node tabindex="0" role="button" data-a-title="{E(title)}" data-a-detail="{E(detail)}">
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/><text class="a-node__title" x="{x+14}" y="{y+24}">{E(title)}</text><text class="a-node__sub" x="{x+14}" y="{y+42}">{E(sub)}</text></g>"""
def edge(x1, y1, x2, y2, label="", dim=False):
    mx = (x1 + x2) / 2
    path = f"M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}" if abs(y1 - y2) > 2 else f"M{x1},{y1} L{x2},{y2}"
    if label and abs(y1 - y2) > 2 and abs(x1 - x2) < 2:
        lab = f'<text class="a-edge__label" x="{x1+8}" y="{(y1+y2)/2+4}">{E(label)}</text>'
    elif label and abs(y1 - y2) <= 2:
        lab = f'<text class="a-edge__label" x="{(x1+x2)/2}" y="{y1-10}" text-anchor="middle">{E(label)}</text>'
    else:
        lab = ""
    return f'<path class="a-edge{" a-edge--dim" if dim else ""}" d="{path}" marker-end="url(#arr)"/>{lab}'

DIAG = f"""
<div class="a-diagram" data-a-diagram tabindex="0">
<div class="a-toolbar a-no-print" style="margin:8px 8px 0;justify-content:flex-end"><button type="button" class="a-btn a-btn--outline" data-a-zoom="out">Zoom out</button><button type="button" class="a-btn a-btn--outline" data-a-zoom="in">Zoom in</button><button type="button" class="a-btn a-btn--outline" data-a-zoom="reset">Reset view</button></div>
<svg class="a-diagram__canvas" data-a-diagram-canvas viewBox="0 0 1180 520" role="img" aria-label="Pipeline: an instruction version is run by the Ola automation inside the Hidden Layer harness with DeepSeek and the GitHub toolkit; each run leaves a Langfuse trace and a usage ledger entry; the SWE-QA-Pro LLM judge turns the run into a score and feedback; GEPA's reflection model reads the feedback and writes a candidate instruction stored as a new version; the candidate is re-run on val for Pareto selection and finally scored on held-out repositories before a human adopts or rejects it.">
<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g class="a-diagram__viewport" data-a-diagram-viewport>
<g class="a-group"><rect x="20" y="20" width="700" height="250" rx="12"/><text x="36" y="46">Execution loop — unchanged production path (Hidden Layer harness)</text></g>
<g class="a-group"><rect x="20" y="300" width="700" height="200" rx="12"/><text x="36" y="326">Optimisation loop — GEPA (new improve/ package, same harness, same model)</text></g>
<g class="a-group"><rect x="760" y="20" width="400" height="480" rx="12"/><text x="776" y="46">Validation — never seen by reflection</text></g>
{node(40,70,200,56,"Instruction version","automation_instruction_versions","Each instruction is a row with id, parent_id and label (baseline, gepa:N, retarget). automations.goal stays the live version; candidates never overwrite it.","a-series-1")}
{node(280,70,200,56,"Automation run","POST /api/automations/<id>/run","The runner fires the same endpoint the console Run button uses, passing instruction_version_id and the question, repository and commit as input. The task is executed by the normal worker.")}
{node(520,70,180,56,"Ola agent","DeepSeek + GitHub toolkit","DeepSeek (flash) drives the agent; tools are the GitHub toolkit over MCP, read-only (get content, get tree, code search). mem0 memory is off so repeats are independent.")}
{node(280,180,200,56,"Trace + transcript + ledger","turns, tool calls, cost, latency","Every run leaves a Langfuse trace, a transcript (function calls = tool calls) and per-request usage receipts (turns, cost in USD). Latency = task finished − started.")}
{node(520,180,180,56,"Evaluator","SWE-QA-Pro judge (DeepSeek)","The benchmark's own judge prompt scores the final answer against the reference on correctness, completeness, relevance, clarity, reasoning (1–10 each). score = total / 50. Feedback text: question, reference, agent answer, the five scores.")}
{node(520,350,180,56,"Reflection LM","DeepSeek, no tools","GEPA's fixed meta-prompt + the reflective dataset (Inputs / Generated Outputs / Feedback for a minibatch of 3 train runs). Output = a new instruction text. Cost logged separately.")}
{node(280,350,200,56,"Candidate version","parent = current","The proposed text is stored as a child version. Accepted if it beats the parent on the minibatch; then scored on val (k=1) and kept on the per-example Pareto frontier.")}
{node(40,350,200,56,"Pareto selection","per-example frontier, val","GEPA keeps every candidate that is best on at least one val example and samples the next parent from that frontier. V1 optimises quality only; cost/latency/turns/tool calls are recorded, not optimised.")}
{node(40,430,200,56,"Stop","100 metric calls · 8 idle rounds","val 10 Q; seed scored from baseline runs. In progress — see tab 4.")}
{node(790,80,340,56,"Train / Val — 4 repos","20 Q each","Train: pint, responses (reflection reads these runs). Val: sanic, dwave-cloud-client (candidate selection).","a-series-3")}
{node(790,180,340,56,"Held-out — 2 unseen repos","20 Q × k=3, tox + docker-py","Repositories never used in optimisation. The instruction is repo-agnostic, so it runs unchanged. Checks that what was learned transfers to code the reflection never saw.","a-series-3")}
{node(790,290,340,56,"Compare v0 vs candidate","quality, cost, latency, turns, tool calls","Each question is run 3 times per version to absorb model nondeterminism. Quality is the objective; the other four are reported as side effects.")}
{node(790,400,340,56,"Human adopts or rejects","sets the live version","No automatic adoption. Adopting = pointing automations.goal at the candidate version; history is kept.","a-series-2")}
{edge(240,98,280,98)}{edge(480,98,520,98)}
{edge(610,126,610,180,"trace")}{edge(520,208,480,208)}
{edge(610,236,610,350,"score + feedback")}
{edge(520,378,480,378)}{edge(280,378,240,378)}
{edge(140,406,140,430)}
{edge(140,350,140,126,"",True)}
{edge(700,98,790,108,"",True)}{edge(700,98,790,208,"",True)}
{edge(960,136,960,180)}{edge(960,236,960,290)}{edge(960,346,960,400)}
</g></svg>
<div class="a-inspector" data-a-inspector aria-live="polite"><p class="a-inspector__title" data-a-inspector-title>Select a box</p><p style="margin:0;color:rgb(var(--text-secondary))" data-a-inspector-body>What that step does appears here.</p></div>
</div>"""

def mrow(label, v0v, cv, fmt, better="up"):
    return f"<tr><th scope=\"row\">{label}</th><td data-numeric>{fmt(v0v)}</td><td data-numeric>{fmt(cv)}</td></tr>"

h2v, h2c = R[('heldout2', 'v0')], R[('heldout2', 'cand')]
appendix_rows = "".join(
    f"<tr><td>{lab}</td><td>{repo}</td>"
    + "".join(f"<td data-numeric>{R[(s,v)]['ok']}/{R[(s,v)]['n']}</td><td data-numeric>${R[(s,v)]['cost']:.3f}</td><td data-numeric>{R[(s,v)]['lat']:.0f}s / {R[(s,v)]['lat90']:.0f}s</td><td data-numeric>{R[(s,v)]['turns']:.1f}</td><td data-numeric>{('n/a' if R[(s,v)]['tools']!=R[(s,v)]['tools'] else f"{R[(s,v)]['tools']:.1f}")}</td>" for v in ('v0', 'cand'))
    + "</tr>" for s, lab, repo in SPLITS)
B = pathlib.Path("/home/ubuntu/repos/Hidden-Layer-Internal/src/hidden_layer/improve/bench/c1")
Q = {}
for fn in ("examples.jsonl", "examples_heldout2.jsonl"):
    for line in (B / fn).read_text().splitlines():
        if not line.strip(): continue
        e = json.loads(line)
        g = e.get("gold") or {}
        Q[e["id"]] = (e.get("question", ""), g.get("answer"), g.get("paths") or [], e.get("kind", ""))
def fmt_gold(g): return E(json.dumps(g, ensure_ascii=False) if isinstance(g, (list, dict)) else str(g))
pq_rows = "".join(
    f"<tr data-split=\"{s}\"><td>{s}</td><td style=\"white-space:nowrap\">{ex}</td><td>{E(Q.get(ex, ('?',None,[],''))[3])}</td><td style=\"min-width:30ch\">{E(Q.get(ex, ('?',None,[],''))[0])}</td>"
    f"<td><code>{fmt_gold(Q.get(ex, ('?',None,[],''))[1])}</code></td><td style=\"word-break:break-all;min-width:22ch\">{'<br>'.join(f'<code>{E(x)}</code>' for x in Q.get(ex, ('?',None,[],''))[2])}</td>"
    f"<td data-numeric>{pq[(s,ex,'v0')][0]}/{pq[(s,ex,'v0')][1]}</td><td data-numeric>{pq[(s,ex,'cand')][0]}/{pq[(s,ex,'cand')][1]}</td></tr>" for s, ex in exs)


QA_RUNS = json.load(open(P / "qa_runs.json"))
QB = pathlib.Path("/home/ubuntu/repos/Hidden-Layer-Internal/src/hidden_layer/improve/bench/qa")
QEX = {json.loads(l)["id"]: json.loads(l) for l in (QB / "examples.jsonl").read_text().splitlines() if l.strip()}
QV0 = (QB / "instruction_v0.md").read_text().strip()
qagg = collections.defaultdict(list)
for r in QA_RUNS: qagg[r["split"]].append(r)
def qa_stat(sp):
    rs = qagg[sp]; m = lambda k: st.mean(r[k] for r in rs if r[k] is not None)
    lat = sorted(r["latency_s"] for r in rs if r["latency_s"] is not None)
    return dict(n=len(rs), q=m("score"), cost=m("cost_usd"), turns=m("turns"), tools=m("tool_calls"), lat=st.median(lat), lat90=lat[max(0, round(.9*len(lat))-1)])
QS = {sp: qa_stat(sp) for sp in ("train", "val", "heldout")}
QLAB = {"train": "Train (pilot, k=1)", "val": "Val (k=3)", "heldout": "Held-out (k=3)"}
def qchart(title, unit, key, fmt):
    rows = "".join(f'<tr><th scope="row">{QLAB[sp]}</th><td data-numeric>{fmt(QS[sp][key])}</td></tr>' for sp in ("train", "val", "heldout"))
    return f'<figure class="a-panel" data-a-chart="bar" data-a-chart-unit="{unit}" data-a-chart-height="200"><figcaption class="a-panel__title">{title}</figcaption><div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">{title}</caption><thead><tr><th scope="col">Split</th><th scope="col" data-numeric>v0</th></tr></thead><tbody>{rows}</tbody></table></div></figure>'
qpq = collections.defaultdict(list)
for r in QA_RUNS: qpq[r["ex"]].append(r["score"])
qrows = "".join(
    f'<tr><td>{QEX[k]["split"]}</td><td style="white-space:nowrap">{k}</td><td>{E(QEX[k]["repo"])}</td><td>{E(QEX[k]["kind"])} · {E(QEX[k]["subkind"])}</td><td style="min-width:36ch">{E(QEX[k]["question"])}</td><td data-numeric>{len(v)}</td><td data-numeric>{st.mean(v)*50:.1f}</td></tr>'
    for k, v in sorted(qpq.items(), key=lambda kv: (["train","val","heldout"].index(QEX[kv[0]]["split"]), kv[0])))
QA_SECTIONS = f"""
<section role="tabpanel" id="p7" aria-labelledby="t7" class="a-section" hidden>
  <h2 class="a-section__title">Bench — SWE-QA-Pro sub-bench: repository-level code questions</h2>
  <p class="a-section__note">Published benchmark (TIGER-Lab, MIT; 260 questions over 26 long-tail Python repos, each pinned to a commit, filtered to need repository exploration). We use 6 repos × 10 questions, drawn at random (seed 20261021) among the ten smallest repos and split by repository, never by v0 score.</p>
  <div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">Sub-bench splits</caption>
  <thead><tr><th scope="col">Split</th><th scope="col">Repositories</th><th scope="col" data-numeric>Questions</th><th scope="col">Role</th></tr></thead><tbody>
  <tr><td>Train</td><td><code>hgrecco/pint</code>, <code>getsentry/responses</code></td><td data-numeric>20</td><td>GEPA reflects on these runs</td></tr>
  <tr><td>Val</td><td><code>sanic-org/sanic</code>, <code>dwavesystems/dwave-cloud-client</code></td><td data-numeric>20</td><td>GEPA selects candidates here</td></tr>
  <tr><td>Held-out</td><td><code>tox-dev/tox</code>, <code>docker/docker-py</code></td><td data-numeric>20</td><td>Never seen during optimisation; final exam</td></tr></tbody></table></div>
  <h3 class="a-section__title" style="margin-top:20px">The instruction being optimised — v0 ({len(QV0)} characters)</h3>
  <div class="a-panel"><pre class="pre">{E(QV0)}</pre></div>
  <p class="a-section__note">Repo-agnostic: each question's repository and commit arrive in the triggering event. Tools: the GitHub toolkit (MCP), read-only.</p>
  <h3 class="a-section__title" style="margin-top:20px">Quality = the benchmark's own LLM judge</h3>
  <dl class="a-meta-list"><div><dt>Prompt</dt><dd>verbatim from SWE-QA-Pro: correctness, completeness, relevance, clarity, reasoning — each 1–10</dd></div><div><dt>Score</dt><dd>sum of the five / 50 (0.1–1.0)</dd></div><div><dt>Judge model</dt><dd>DeepSeek flash, temperature 0, inside the harness (the benchmark supports a DeepSeek judge)</dd></div><div><dt>Judge checks</dt><dd>reference answer → 50/50; first third of it → ~32; wrong one-liner → 6–12; same answer judged 3× → ±1 point; DeepSeek v4-pro was not stricter (−1.4) and costs 3.5×</dd></div><div><dt>Feedback to GEPA</dt><dd>question, reference answer, agent answer, the five scores</dd></div></dl>
  <h3 class="a-section__title" style="margin-top:20px">Other metrics (observed, not optimised in this stage)</h3>
  <dl class="a-meta-list"><div><dt>Cost</dt><dd>USD of all LLM requests in the run (usage ledger); judge calls booked separately</dd></div><div><dt>Latency</dt><dd>task finished − started, seconds (queue excluded)</dd></div><div><dt>Turns</dt><dd>LLM requests in the run</dd></div><div><dt>Tool calls</dt><dd>function-call items in the run's transcript</dd></div></dl>
</section>

<section role="tabpanel" id="p8" aria-labelledby="t8" class="a-section" hidden>
  <h2 class="a-section__title">Baseline — v0 already scores ≈ 0.91</h2>
  <div class="kv">
    <div class="a-metric"><div class="a-metric__label">Val quality</div><div class="a-metric__value">{QS['val']['q']*100:.1f}%</div><div class="a-metric__delta">{QS['val']['n']} runs · 20 Q × 3</div></div>
    <div class="a-metric"><div class="a-metric__label">Held-out quality</div><div class="a-metric__value">{QS['heldout']['q']*100:.1f}%</div><div class="a-metric__delta">{QS['heldout']['n']} runs · 20 Q × 3</div></div>
    <div class="a-metric"><div class="a-metric__label">Run-to-run spread</div><div class="a-metric__value">±0.04</div><div class="a-metric__delta">same question, 3 runs</div></div>
  </div>
  <div class="a-grid a-grid--halves" style="margin-top:16px">
    {qchart('Quality (judge total / 50)', '%', 'q', lambda x: f"{x*100:.1f}%")}
    {qchart('Cost per run (USD)', '$', 'cost', lambda x: f"{x:.3f}")}
  </div>
  <div class="a-grid a-grid--halves" style="margin-top:16px">
    {qchart('Turns per run', '', 'turns', lambda x: f"{x:.1f}")}
    {qchart('Tool calls per run', '', 'tools', lambda x: f"{x:.1f}")}
  </div>
  <div class="a-grid a-grid--halves" style="margin-top:16px">
    {qchart('Latency, median (s)', 's', 'lat', lambda x: f"{x:.0f}")}
    {qchart('Latency, p90 (s)', 's', 'lat90', lambda x: f"{x:.0f}")}
  </div>
  <div class="a-callout a-callout--decision" style="margin-top:16px"><strong>Where the headroom is.</strong> Lost points are correctness and completeness (≈ 7.8/10); relevance and clarity are ≈ 9–9.5. Questions averaging below 0.8: 1 in val, 2 in held-out. A gain of a few points is measurable at this spread; the ceiling looks like ≈ 0.95.</div>
  <h3 class="a-section__title" style="margin-top:20px">All 50 baseline questions</h3>
  <div class="a-table-scroll"><table class="a-table" data-a-sticky-columns="2"><caption class="a-visually-hidden">Per-question baseline scores</caption><thead><tr><th scope="col">Split</th><th scope="col">ID</th><th scope="col">Repo</th><th scope="col">Type</th><th scope="col">Question</th><th scope="col" data-numeric>runs</th><th scope="col" data-numeric>mean /50</th></tr></thead><tbody>{qrows}</tbody></table></div>
  <p class="a-section__note">Train has only the 10 pilot questions so far (k=1); the other 10 train questions are used by GEPA itself.</p>
</section>
"""


import importlib.util as _ilu
_JUDGE = pathlib.Path("/home/ubuntu/repos/Hidden-Layer-Internal/src/hidden_layer/improve/bench/qa/judge_prompt.txt").read_text().replace("{{", "{").replace("}}", "}")
_g = pathlib.Path("/home/ubuntu/repos/gepa/src/gepa/strategies/instruction_proposal.py").read_text()
_REFL = re.search(r'default_prompt_template = """(.*?)"""', _g, re.S).group(1)
_SLOTS = [
    ("<curr_param>", "The current instruction: the parent candidate GEPA selected from the Pareto frontier (v0 in round 1)."),
    ("<side_info>", "The 3 train examples of this round's minibatch, each rendered as: <b>Inputs</b> (the question) · <b>Generated Outputs</b> (the agent's full reply) · <b>Feedback</b> (judge feedback: repo, commit, question, reference answer, agent answer, 5 judge scores; plus one execution-trace line: turns, tool calls + tool names, cost, latency)."),
    ("Output", "GEPA takes the text inside the ``` block as the new candidate instruction. Reflection model: DeepSeek flash via the Hidden Layer model binding, no tools, max 32k output tokens."),
]
_JSLOTS = [
    ("Inputs", "The question, the SWE-QA-Pro reference answer, and the agent's final answer (last <code>&lt;finish&gt;…&lt;/finish&gt;</code> block, else the whole reply)."),
    ("Model", "DeepSeek flash, temperature 0; reply must parse as 5 integers in [1, 10], up to 3 attempts."),
    ("Score", "sum of the 5 dimensions / 50 — the number GEPA maximizes."),
]
def _slot_rows(xs): return "".join(f"<tr><td><code>{E(a)}</code></td><td>{b}</td></tr>" for a, b in xs)
PROMPTS_SECTION = f"""
<section role="tabpanel" id="p9" aria-labelledby="t9" class="a-section" hidden>
  <h2 class="a-section__title">Appendix E — the two fixed prompts in the loop</h2>
  <p class="a-section__note">Neither prompt is optimized. The judge scores every run; the reflection meta-prompt writes every candidate. Both are used verbatim.</p>
  <h3 class="a-section__title">1. Judge prompt (official SWE-QA-Pro, unchanged)</h3>
  <div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">Judge inputs</caption><tbody>{_slot_rows(_JSLOTS)}</tbody></table></div>
  <div class="a-panel" style="margin-top:8px"><pre class="pre">{E(_JUDGE)}</pre></div>
  <h3 class="a-section__title" style="margin-top:20px">2. GEPA reflection meta-prompt (GEPA default, <code>InstructionProposalSignature.default_prompt_template</code>, not overridden)</h3>
  <div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">Reflection slots</caption><tbody>{_slot_rows(_SLOTS)}</tbody></table></div>
  <div class="a-panel" style="margin-top:8px"><pre class="pre">{E(_REFL)}</pre></div>
</section>
"""
exec(open("/home/ubuntu/Documents/report/gepa_section.py").read()); import json as _j; GEPA_SECTION="".join(GEPA_SECTION.replace("__"+k+"__", str(v)) for k,v in [("_",0)]) if False else GEPA_SECTION
for _k,_v in _j.load(open("/home/ubuntu/Documents/report/gepa_snap.json")).items(): GEPA_SECTION=GEPA_SECTION.replace("__"+_k+"__", str(_v))
BODY = f"""
<style>
.dl ins{{background:color-mix(in srgb, var(--a-series-2, #2a7) 22%, transparent);text-decoration:none;border-radius:3px;padding:0 2px}}
.dl del{{background:color-mix(in srgb, var(--a-series-4, #c44) 22%, transparent);text-decoration:line-through;border-radius:3px;padding:0 2px}}
.dl p{{margin:0 0 .7em;line-height:1.5;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82rem;white-space:pre-wrap}}
.pre{{white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82rem;line-height:1.5;margin:0}}
.kv{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}}
.a-node.a-series-1 rect{{stroke-width:2}}
</style>

<nav class="a-panel" data-a-tabs aria-label="Pages">
  <div role="tablist">
    <button role="tab" id="t1" aria-controls="p1" aria-selected="true">1 · Pipeline</button>
    <button role="tab" id="t7" aria-controls="p7" aria-selected="false">2 · Bench &amp; prompt</button>
    <button role="tab" id="t8" aria-controls="p8" aria-selected="false">3 · Baseline</button>
    <button role="tab" id="t10" aria-controls="p10" aria-selected="false">4 · GEPA (interim)</button>
    <button role="tab" id="t2" aria-controls="p2" aria-selected="false">Appendix A · C1 task</button>
    <button role="tab" id="t3" aria-controls="p3" aria-selected="false">Appendix B · C1 prompt diff</button>
    <button role="tab" id="t4" aria-controls="p4" aria-selected="false">Appendix C · C1 results</button>
    <button role="tab" id="t5" aria-controls="p5" aria-selected="false">Appendix D · C1 data</button>
    <button role="tab" id="t9" aria-controls="p9" aria-selected="false">Appendix E · Judge &amp; reflection prompts</button>
  </div>

<section role="tabpanel" id="p1" aria-labelledby="t1" class="a-section">
  <h2 class="a-section__title">Experiment setup — one closed loop, all inside the Hidden Layer harness</h2>
  <p class="a-section__note">Top: the normal automation path. Bottom: GEPA bolted on as a module. Right: validation data the optimiser never sees. Click a box.</p>
  {DIAG}
  <div class="kv" style="margin-top:16px">
    <div class="a-metric"><div class="a-metric__label">Execution model</div><div class="a-metric__value" style="font-size:1.1rem">DeepSeek</div><div class="a-metric__delta">+ GitHub toolkit (MCP), mem0 off</div></div>
    <div class="a-metric"><div class="a-metric__label">Reflection model</div><div class="a-metric__value" style="font-size:1.1rem">DeepSeek</div><div class="a-metric__delta">same binding, no tools</div></div>
    <div class="a-metric"><div class="a-metric__label">Objective (V1)</div><div class="a-metric__value" style="font-size:1.1rem">quality only</div><div class="a-metric__delta">cost · latency · turns · tool calls observed</div></div>
    <div class="a-metric"><div class="a-metric__label">Repeats</div><div class="a-metric__value" style="font-size:1.1rem">k = 3</div><div class="a-metric__delta">per question per version</div></div>
  </div>
</section>

<section role="tabpanel" id="p2" aria-labelledby="t2" class="a-section" hidden>
  <h2 class="a-section__title">Appendix A — first task C1: codebase fact Q&amp;A at a pinned commit (too easy; superseded by SWE-QA-Pro)</h2>
  <p class="a-prose">The automation is asked one question about a repository and must answer from the code at a fixed commit, returning <code>{{"answer", "path"}}</code>. Questions are of seven mechanical types (default value, locate file, inheritance, call chain, field set, count, cross-file count); gold answers were checked by hand on a local checkout. Score is 1 only if both the answer and the file path are right.</p>
  <div class="a-grid a-grid--halves">
    <div class="a-panel"><div class="a-panel__head"><h3 class="a-panel__title">Repo 1 — train / val / held-out</h3></div>
      <dl class="a-meta-list"><div><dt>Repository</dt><dd><code>openai/openai-agents-python</code></dd></div><div><dt>Commit</dt><dd><code>17d994b</code> (v0.24.0)</dd></div><div><dt>Scope</dt><dd><code>src/agents/</code></dd></div><div><dt>Questions</dt><dd>20 → train 8 · val 6 · held-out 6</dd></div><div><dt>Role</dt><dd>GEPA learns from train, selects on val; held-out checks overfitting</dd></div></dl></div>
    <div class="a-panel"><div class="a-panel__head"><h3 class="a-panel__title">Repo 2 — held-out 2 (distribution shift)</h3></div>
      <dl class="a-meta-list"><div><dt>Repository</dt><dd><code>pydantic/pydantic-ai</code></dd></div><div><dt>Commit</dt><dd><code>bf9a243</code> (v2.9.1)</dd></div><div><dt>Scope</dt><dd><code>pydantic_ai_slim/pydantic_ai/</code></dd></div><div><dt>Questions</dt><dd>10, same seven types</dd></div><div><dt>Role</dt><dd>Never touched during optimisation; repo slug + commit substituted into the instruction</dd></div></dl></div>
  </div>
  <h3 class="a-section__title" style="margin-top:20px">The instruction being optimised — v0 ({len(v0)} characters)</h3>
  <div class="a-panel"><pre class="pre">{E(v0)}</pre></div>
  <h3 class="a-section__title" style="margin-top:20px">What the evaluator hands back (score + feedback = GEPA's "side information")</h3>
  <div class="a-panel"><pre class="pre">Question: What is the default value of `DEFAULT_MAX_ARCHIVE_MEMBERS`?
Gold answer: 100000
Accepted path(s): src/agents/run_config.py
Agent answer: 'DEFAULT_MAX_ARCHIVE_MEMBERS = 100_000'
Agent path: 'src/agents/run_config.py'
Answer match: no · Path match: yes → score 0
Execution trace: status=done; turns=5; tool_calls=3 (load_toolkit, GITHUB_SEARCH_CODE, GITHUB_GET_REPOSITORY_CONTENT); cost_usd=0.0112; latency_s=14</pre></div>
  <h3 class="a-section__title" style="margin-top:20px">Metric definitions — five numbers per run</h3>
  <div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">Metric definitions</caption>
  <thead><tr><th scope="col">Metric</th><th scope="col">Definition (one run = one question answered once)</th><th scope="col">Source</th><th scope="col">Unit</th><th scope="col">Role in V1</th></tr></thead>
  <tbody>
  <tr><td><strong>Quality</strong></td><td>1 if the normalised <code>answer</code> equals the gold answer <em>and</em> <code>path</code> is one of the accepted files; otherwise 0. No JSON, timeout or failure = 0. Normalisation: trim, strip quotes/backticks, lower-case, drop trailing period, <code>100_000</code> → <code>100000</code>, 1 GiB / 2**30 → 1073741824, None ≡ null; list answers compared as sets.</td><td>Deterministic evaluator (<code>evaluators/c1.py</code>), no LLM</td><td>0 / 1; reported as share of runs</td><td><strong>Objective</strong> — the only score GEPA optimises</td></tr>
  <tr><td><strong>Cost</strong></td><td>Sum of the price of every LLM request made by the run (prompt + completion tokens × DeepSeek list price). Failed runs still count what they spent. Reflection calls are booked separately, not here.</td><td>Hidden Layer usage ledger (<code>usage_events_local</code>), joined on the run's trace id</td><td>USD per run</td><td>Observed only</td></tr>
  <tr><td><strong>Latency</strong></td><td>Wall-clock time from the worker starting the task to the task reaching a terminal state; queue wait is excluded. Network-sensitive, so reported as median and p90.</td><td><code>tasks.finished − tasks.started</code></td><td>seconds</td><td>Observed only</td></tr>
  <tr><td><strong>Turns</strong></td><td>Number of LLM requests the agent made in the run — each "model → tool → model" round is one turn. Deterministic, not affected by network.</td><td>Usage receipts per run (one per request)</td><td>count</td><td>Observed only</td></tr>
  <tr><td><strong>Tool calls</strong></td><td>Number of tool invocations in the run (e.g. get file content, get tree, code search, load toolkit).</td><td>The run&#39;s own transcript: function-call items in the task session (<code>agent_messages</code>)</td><td>count</td><td>Observed only</td></tr>
  </tbody></table></div>
  <p class="a-section__note">Every number on page 4 is an average over k = 3 runs per question (model output is nondeterministic). pass^3 (all three runs correct) is in the appendix per question.</p>
</section>

<section role="tabpanel" id="p3" aria-labelledby="t3" class="a-section" hidden>
  <h2 class="a-section__title">Appendix B — C1 prompt: v0 → candidate, after one GEPA reflection</h2>
  <p class="a-section__note">One reflection call (3 train runs as evidence, DeepSeek, 16 s, $0.004) produced the right-hand text. {len(v0)} → {len(cand)} characters; <ins style="background:color-mix(in srgb, var(--a-series-2,#2a7) 22%, transparent);text-decoration:none">green</ins> = sentences not present in v0; everything in v0 survives, rephrased.</p>
  <div class="a-grid a-grid--halves dl">
    <div class="a-panel"><div class="a-panel__head"><h3 class="a-panel__title">v0 — baseline <code>0d6e62af</code></h3></div>{diff_left}</div>
    <div class="a-panel"><div class="a-panel__head"><h3 class="a-panel__title">Candidate — <code>0b131d92</code> (gepa:1)</h3></div>{diff_right}</div>
  </div>
  <div class="a-callout" style="margin-top:16px"><strong>What it learned, mapped to the baseline's failure modes.</strong>
    <ol class="a-prose" style="margin:.4em 0 0 1.2em"><li>Final message = one JSON object, no fences, no prose → fixes "JSON wrapped in explanation".</li><li><code>answer</code> is the bare value / array / path → fixes "value with explanation in parentheses" (the biggest cause, 14 of 15 baseline misses).</li><li><code>path</code> is a repository-relative file, not a URL or directory.</li><li>Read at the pinned commit, never from memory or the default branch; code-search first when the tree is too large.</li></ol>
    <p class="a-prose" style="margin-top:.5em">It also wrote the three training facts into the prompt as examples (<code>100_000 → "100000"</code>, <code>Handoff</code> lives in <code>handoffs/__init__.py</code>, the field list of <code>ModelRetryBackoffSettings</code>) — the "niche factual information" GEPA's meta-prompt asks for. These are procedural rules, not new reasoning.</p></div>
</section>

<section role="tabpanel" id="p4" aria-labelledby="t4" class="a-section" hidden>
  <h2 class="a-section__title">Appendix C — C1 results: GEPA candidate vs v0 (one reflection round)</h2>
  <p class="a-section__note">V1 optimised <strong>quality only</strong>. Cost, latency, turns and tool calls were recorded but were not part of the objective; their movement is a side effect.</p>
  <div class="kv">
    <div class="a-metric"><div class="a-metric__label">Held-out 2 quality (new repo)</div><div class="a-metric__value">{pct(h2v['q'])} → {pct(h2c['q'])}</div><div class="a-metric__delta" data-trend="up">{h2v['ok']}/{h2v['n']} → {h2c['ok']}/{h2c['n']} correct</div></div>
    <div class="a-metric"><div class="a-metric__label">Repo 1, all 20 questions</div><div class="a-metric__value">{pct(r1['v0']['ok']/r1['v0']['n'])} → {pct(r1['cand']['ok']/r1['cand']['n'])}</div><div class="a-metric__delta" data-trend="up">{r1['v0']['ok']}/{r1['v0']['n']} → {r1['cand']['ok']}/{r1['cand']['n']}</div></div>
    <div class="a-metric"><div class="a-metric__label">Cost per run (held-out 2)</div><div class="a-metric__value">${h2v['cost']:.3f} → ${h2c['cost']:.3f}</div><div class="a-metric__delta" data-trend="up">not optimised, {(1-h2c['cost']/h2v['cost'])*100:.0f}% lower</div></div>
    <div class="a-metric"><div class="a-metric__label">Optimisation spend</div><div class="a-metric__value">≈ $0.45</div><div class="a-metric__delta">24 runs + 1 reflection ($0.004)</div></div>
  </div>
  <div class="a-grid a-grid--halves" style="margin-top:16px">
    {chart('c-q','Quality — share of runs with correct answer and path','%','q',lambda x: f"{x*100:.0f}%")}
    {chart('c-cost','Cost per run (USD)','$','cost',lambda x: f"{x:.3f}")}
  </div>
  <div class="a-grid a-grid--halves" style="margin-top:16px">
    {chart('c-turns','Turns per run (LLM requests)','','turns',lambda x: f"{x:.1f}")}
    {chart('c-tools','Tool calls per run','','tools',lambda x: f"{x:.1f}")}
  </div>
  <div class="a-grid a-grid--halves" style="margin-top:16px">
    {chart('c-lat','Latency per run — median seconds','s','lat',lambda x: f"{x:.0f}")}
    <figure class="a-panel" data-a-chart="stacked-bar" data-a-chart-height="240">
      <figcaption class="a-panel__title">Why v0 missed — all format, no wrong facts</figcaption>
      <div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">Baseline misses by cause</caption>
      <thead><tr><th scope="col">Set</th><th scope="col" data-numeric>Value wrapped in explanation</th><th scope="col" data-numeric>Prose / Markdown around JSON</th><th scope="col" data-numeric>Factual (read wrong version)</th></tr></thead>
      <tbody><tr><th scope="row">Repo 1 baseline run (60)</th><td data-numeric>14</td><td data-numeric>0</td><td data-numeric>1</td></tr>
      <tr><th scope="row">Held-out 2, v0 (30)</th><td data-numeric>2</td><td data-numeric>3</td><td data-numeric>0</td></tr></tbody></table></div>
      <p class="a-section__note">The one factual miss (c1-06) was an environment limit — a 50k-character cap on tool results hid the file; after raising the cap v0 also answers it. It is not something the instruction could fix.</p>
    </figure>
  </div>
  <div class="a-callout a-callout--risk" style="margin-top:16px"><strong>Read with care.</strong> The benchmark is easy: val saturated after one round, so GEPA had nothing left to propose. Gains are procedural (output contract, read-at-commit), not reasoning. Held-out 2 is 10 questions; k=3 noise is about ±1–2 correct out of 30 — the 5-run gap is above that.</div>
</section>

{QA_SECTIONS}
<section role="tabpanel" id="p5" aria-labelledby="t5" class="a-section" hidden>
  <h2 class="a-section__title">Appendix D — C1 data</h2>
  <h3 class="a-section__title">A. All five metrics by split (latest k=3 per question)</h3>
  <div class="a-table-scroll"><table class="a-table" data-a-sticky-columns="1"><caption class="a-visually-hidden">Metrics by split and version</caption>
  <thead><tr><th scope="col" rowspan="2">Split</th><th scope="col" rowspan="2">Repo</th><th scope="col" colspan="5">v0</th><th scope="col" colspan="5">Candidate</th></tr>
  <tr><th scope="col" data-numeric>correct</th><th scope="col" data-numeric>$/run</th><th scope="col" data-numeric>lat med/p90</th><th scope="col" data-numeric>turns</th><th scope="col" data-numeric>tools</th><th scope="col" data-numeric>correct</th><th scope="col" data-numeric>$/run</th><th scope="col" data-numeric>lat med/p90</th><th scope="col" data-numeric>turns</th><th scope="col" data-numeric>tools</th></tr></thead>
  <tbody>{appendix_rows}</tbody></table></div>
  <p class="a-section__note">Repo-1 numbers use the re-runs after the tool-result cap was raised for c1-06 and c1-19 (the earlier runs are in the experiment log). Tool calls are counted from each run's own transcript (function-call items in the task session). An earlier count from Langfuse TOOL spans undercounted by about one call per run (trace ingestion lags the end of the task) and is no longer used.</p>
  <h3 class="a-section__title" style="margin-top:20px">B. All 30 questions, gold answers and per-question correct runs (out of 3)</h3>
  <p class="a-section__note">The question text is what the agent receives in the triggering event (<code>input.question</code>); the instruction adds the repo and commit. Accepted path = any of the listed files.</p>
  <div class="a-table-scroll"><table class="a-table" data-a-sticky-columns="2"><caption class="a-visually-hidden">Questions, gold answers and per-question results</caption><thead><tr><th scope="col">Split</th><th scope="col">ID</th><th scope="col">Type</th><th scope="col">Question</th><th scope="col">Gold answer</th><th scope="col">Accepted path(s)</th><th scope="col" data-numeric>v0</th><th scope="col" data-numeric>Candidate</th></tr></thead><tbody>{pq_rows}</tbody></table></div>
  <h3 class="a-section__title" style="margin-top:20px">C. Run log</h3>
  <div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">Run log</caption><thead><tr><th scope="col">Run</th><th scope="col">What</th><th scope="col">Result</th></tr></thead><tbody>
  <tr><td>Run 0</td><td>v0 in Chinese, 20 Q × 3</td><td>quality 0.30 — superseded, all artifacts switched to English</td></tr>
  <tr><td>Run 1</td><td>v0 in English, 20 Q × 3</td><td>quality 0.75; 14 format misses, 1 factual (c1-06)</td></tr>
  <tr><td>V1a / V1b</td><td>GEPA starts</td><td>no candidate — adapter missing an optional GEPA attribute (fixed, 1 line); then DeepSeek balance exhausted</td></tr>
  <tr><td>V1c</td><td>GEPA, train 8 (minibatch 3), val 6</td><td>round 1: candidate accepted 3/3, val 6/6; round 2 nothing to learn → stopped by hand. 24 runs + 1 reflection ≈ $0.45</td></tr>
  <tr><td>Validation</td><td>candidate, 20 Q × 3</td><td>train 1.00, val 1.00, held-out 0.78 (c1-06 blocked by the 50k tool-result cap; c1-19 question ambiguous)</td></tr>
  <tr><td>Follow-up A</td><td>cap made configurable (400k for the experiment), c1-19 reworded; c1-06/c1-19 re-run</td><td>v0 6/6, candidate 6/6</td></tr>
  <tr><td>Follow-up B</td><td>held-out 2 (pydantic-ai), v0 and candidate × 3</td><td>v0 {h2v['ok']}/{h2v['n']}, candidate {h2c['ok']}/{h2c['n']} (first candidate attempt lost to a provider balance error, re-run)</td></tr>
  </tbody></table></div>
  <h3 class="a-section__title" style="margin-top:20px">D. Configuration</h3>
  <dl class="a-meta-list"><div><dt>Instance</dt><dd>Hidden Layer on the VM, Postgres <code>hl_improve</code>, tenant <code>devinlive</code>, <code>HL_MEMORY_BACKEND=off</code>, <code>HL_MCP_RESULT_MAX_CHARS=400000</code></dd></div>
  <div><dt>Models</dt><dd>DeepSeek (flash) for execution and reflection, via the commander binding</dd></div>
  <div><dt>GEPA</dt><dd>default reflective mutation, per-example Pareto frontier, minibatch 3, val k=1; stop = 400 metric calls · <code>gepa.stop</code> file · 8 rounds without improvement</dd></div>
  <div><dt>Evaluator</dt><dd>last JSON object with <code>answer</code>; normalised exact match (quotes, case, trailing period, <code>_</code> in numbers, GiB/2**30, None/null); sets compared as sets; path ∈ accepted paths</dd></div>
  <div><dt>Spend</dt><dd>≈ 275 valid runs ≈ $5.7 by the ledger (+ $1.26 for Run 0); two outages (provider balance, instance quota) cost ≈ 60 failed runs</dd></div>
  <div><dt>Code</dt><dd>branch <code>devin/1792547019-improve-s1-mem0-versions</code>: <code>hidden_layer.improve</code> (runner, evaluator, GEPA adapter, reflection, CLI), instruction versions table, <code>improve_runs</code> ledger, memory off switch</dd></div></dl>
</section>
{PROMPTS_SECTION}
{GEPA_SECTION}
</nav>
"""
OUT.write_text(BODY)
print("body", len(BODY), "new sentences", n_new)
for k in sorted(R): print(k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in R[k].items()})
