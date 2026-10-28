import json as _j, re as _re, html as _h, difflib as _dl, collections as _co
_R = "/home/ubuntu/Documents/report/"
_X = _j.load(open(_R + "gepa_viz.json")); _V = _j.load(open(_R + "gepa_val.json")); _ST = _V["stats"]
_C = _j.load(open("/home/ubuntu/improve-runs/v15-qa-gepa-2/candidates.json"))
TXT = {"v0": _C[0]["instruction"], "c1": _C[1]["instruction"], "c2": _C[2]["instruction"], "c3": open(_R + "c3.txt").read(), "c4": _C[4]["instruction"]}
_E = _h.escape
_KS = ("v0", "c1", "c2", "c3", "c4")
_REPO = _re.compile(r"Domain-specific|repository-specific|Known repository", _re.I)

def _fig(kind, title, head, rows, unit="", h=240, note="", extra=""):
    th = "".join(f'<th scope="col"{" data-numeric" if i else ""}>{x}</th>' for i, x in enumerate(head))
    body = "".join("<tr><th scope=\"row\">" + r[0] + "</th>" + "".join(f"<td data-numeric>{c}</td>" for c in r[1:]) + "</tr>" for r in rows)
    n = f'<p class="a-section__note">{note}</p>' if note else ""
    return (f'<figure class="a-panel" data-a-chart="{kind}" data-a-chart-unit="{unit}" data-a-chart-height="{h}"{extra}>'
            f'<figcaption class="a-panel__title">{title}</figcaption><div class="a-table-scroll"><table class="a-table">'
            f'<caption class="a-visually-hidden">{title}</caption><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>{n}</figure>')

def _lost(q): return f"{(1 - q) * 50:.1f}"
VIZ_TRAJ = _fig("bar", "Points lost per answer on val (out of 50, lower is better)", ["Version", "points lost"],
                [[k, _lost(_ST[k]["q"])] for k in _KS], h=220,
                note="Same 10 val questions. v0 = mean of 3 runs per question; candidates = 1 run per question. c1 and c2 were accepted in sequence; c3 (child of c2) and c4 (second child of c1) did not beat c2.")
_D = ("correctness", "completeness", "relevance", "clarity", "reasoning")
VIZ_DIMS = _fig("bar", "Where the points are lost — judge dimension, points lost out of 10", ["Dimension", "v0", "c1", "c2"],
                [[d] + [f"{10 - _X['dims'][k][d]:.2f}" for k in ("v0", "c1", "c2")] for d in _D], h=240,
                note="Gains are concentrated in correctness, completeness and reasoning; relevance and clarity were already near the ceiling.")
_ids = _V["ids"]
def _short(e): return e.replace("qa-dwave-cloud-client-", "dwave-").replace("qa-", "")
VIZ_PERQ = _fig("bar", "Per question — points lost (out of 50)", ["Question", "v0 (mean of 3)", "c2"],
                [[_short(e), _lost(_ST["v0"]["per"][e]), _lost(_ST["c2"]["per"][e])] for e in _ids], h=260,
                note="v0 run-to-run range per question: " + "; ".join(f"{_short(e)} {min(r):.2f}–{max(r):.2f}" for e, r in _X["v0runs"].items()) + ". dwave-10's v0 mean is pulled down by a single 0.52 run, so its gap is mostly noise; sanic-06, sanic-09 and dwave-01 are cases where c2 beats every v0 run.")
VIZ_EFF = _fig("bar", "Behaviour per run on val", ["Version", "turns", "tool calls", "answer length (k chars)"],
               [[k, f"{_ST[k]['turns']:.1f}", f"{_ST[k]['tools']:.1f}", f"{_ST[k]['anslen'] / 1000:.1f}"] for k in _KS], h=240,
               note="c2 answers are ~75% longer with about the same number of turns and tool calls as v0; c3 explores more (17 turns, 22 tool calls) without scoring higher.")

def _sections(t):
    out, cur, typ = [], [], "general"
    for line in t.split("\n"):
        if line.startswith("## "):
            if cur: out.append((typ, "\n".join(cur)))
            cur, typ = [line], ("repo" if _REPO.search(line) else "general")
        else:
            cur.append(line)
    if cur: out.append((typ, "\n".join(cur)))
    return out
def _comp(t):
    g = sum(len(s) for ty, s in _sections(t) if ty == "general"); r = sum(len(s) for ty, s in _sections(t) if ty == "repo"); return g, r
VIZ_COMP = _fig("stacked-bar", "What the instruction is made of (k characters)", ["Version", "general answering strategy", "train-repo facts (pint, responses)"],
                [[k, f"{_comp(TXT[k])[0] / 1000:.1f}", f"{_comp(TXT[k])[1] / 1000:.1f}"] for k in _KS], h=240,
                note="Split by section heading: sections titled “Domain-specific …” / “Known repository-specific …” count as train-repo facts, everything else as general strategy. None of the four versions mentions a val or held-out repository.")

_G = "background:color-mix(in srgb, var(--a-series-2,#2a7) 22%, transparent);text-decoration:none"
_O = "background:color-mix(in srgb, var(--a-series-3,#d80) 24%, transparent);text-decoration:none"
_BOX = "max-height:520px;overflow:auto;font-size:12.5px;line-height:1.45;white-space:pre-wrap;margin:0"
def _colored(t):
    parts = []
    for ty, s in _sections(t):
        parts.append(f'<ins style="{_O if ty == "repo" else _G}">{_E(s)}</ins>')
    return f'<pre class="a-prose" style="{_BOX}">' + "\n".join(parts) + "</pre>"
def _diff(a, b):
    A, B = a.split("\n"), b.split("\n"); sm = _dl.SequenceMatcher(a=A, b=B, autojunk=False); out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        for x in B[j1:j2]:
            out.append(_E(x) if tag == "equal" else f'<ins style="{_G}">{_E(x)}</ins>')
    kept = sum(i2 - i1 for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag == "equal")
    return f'<pre class="a-prose" style="{_BOX}">' + "\n".join(out) + "</pre>", kept, len(B)
_d12, _kept, _nb = _diff(TXT["c1"], TXT["c2"])
VIZ_DIFF = f"""
  <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr);gap:16px;align-items:start;margin-top:12px">
    <div class="a-panel"><div class="a-panel__head"><h4 class="a-panel__title">v0 — seed <code>001a4209</code> ({len(TXT['v0'])} chars)</h4></div><pre class="a-prose" style="{_BOX}">{_E(TXT['v0'])}</pre></div>
    <div class="a-panel"><div class="a-panel__head"><h4 class="a-panel__title">c2 — best on val <code>3120b6f2</code> ({len(TXT['c2']):,} chars)</h4></div>{_colored(TXT['c2'])}</div>
  </div>
  <p class="a-section__note"><ins style="{_G}">Green</ins> = general answering strategy (transferable). <ins style="{_O}">Orange</ins> = facts about the two train repositories, copied in from judge feedback (reference answers). Scroll the right panel for the full text.</p>
  <details class="a-disclosure" style="margin-top:8px"><summary>c1 → c2: what the second accepted reflection step changed ({_nb - _kept} of {_nb} lines new)</summary>
    <div class="a-panel" style="margin-top:8px">{_d12}</div>
    <p class="a-section__note"><ins style="{_G}">Green</ins> = line not present in c1.</p></details>"""

_EXK = "qa-sanic-06"; _ex = _X["ex"][_EXK]
def _scores(fb):
    m = _re.search(r"Judge scores: (.*?); total (\d+)/50", fb); d = dict(_re.findall(r"(\w+) (\d+)/10", m.group(1))); return d, m.group(2)
def _q(fb): return _re.search(r"Question: (.*)", fb).group(1)
def _ref(fb):
    i, j = fb.find("Reference answer:"), fb.find("\nAgent answer:"); return fb[i + 17:j].strip()
_v0r = _ex["v0"][0]; _c2r = _ex["c2"]
def _sc_table():
    a, ta = _scores(_v0r["fb"]); b, tb = _scores(_c2r["fb"])
    rows = "".join(f"<tr><th scope=\"row\">{d}</th><td data-numeric>{a[d]}</td><td data-numeric>{b[d]}</td></tr>" for d in _D)
    return (f'<div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">Judge scores</caption><thead><tr><th scope="col">Judge dimension</th>'
            f'<th scope="col" data-numeric>v0</th><th scope="col" data-numeric>c2</th></tr></thead><tbody>{rows}'
            f'<tr><th scope="row"><strong>total / 50</strong></th><td data-numeric><strong>{ta}</strong></td><td data-numeric><strong>{tb}</strong></td></tr></tbody></table></div>')
VIZ_EX = f"""
  <p class="a-prose"><strong>{_E(_EXK)}</strong> (sanic @ 57d44f2) — “{_E(_q(_c2r['fb']))}” v0 scores {', '.join(f"{r['score']:.2f}" for r in _ex['v0'])} on its three runs; c2 scores {_c2r['score']:.2f}. Shown: the v0 run that scored {_v0r['score']:.2f} vs the c2 run.</p>
  <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr);gap:16px;align-items:start">{_sc_table()}
    <details class="a-disclosure"><summary>Reference answer (what the judge compares against)</summary><pre class="a-prose" style="{_BOX}">{_E(_ref(_c2r['fb']))}</pre></details></div>
  <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;align-items:start;margin-top:12px">
    <div class="a-panel"><div class="a-panel__head"><h4 class="a-panel__title">v0 answer ({len(_v0r['out']):,} chars)</h4></div><pre class="a-prose" style="{_BOX}">{_E(_v0r['out'])}</pre></div>
    <div class="a-panel"><div class="a-panel__head"><h4 class="a-panel__title">c2 answer ({len(_c2r['out']):,} chars)</h4></div><pre class="a-prose" style="{_BOX}">{_E(_c2r['out'])}</pre></div>
  </div>
  <p class="a-section__note">What changed in the answer, read side by side: c2 opens with a “Short answer” paragraph, links every file at the pinned commit, and has an explicit “pipeline, in execution order” section starting from the entry loop — the behaviours its general-strategy section asks for (direct answer first, trace from the entry point, commit-pinned citations). v0 finds the same core code (buffer scan in <code>http1_request_header</code>) but loses 2 points on correctness and 1 each on completeness, clarity and reasoning.</p>"""

def _scatter(title, xkey, xlab, xfmt, note=""):
    W, H, L, B, T, Rm = 460, 300, 74, 44, 16, 24
    pts = [(k, _ST[k][xkey], _ST[k]["q"]) for k in _KS]
    xs = [p[1] for p in pts]; x0, x1 = min(xs), max(xs); pad = (x1 - x0) * 0.15 or 1; x0 -= pad; x1 += pad
    y0, y1 = 0.88, 0.97
    X = lambda v: L + (v - x0) / (x1 - x0) * (W - L - Rm); Y = lambda v: H - B - (v - y0) / (y1 - y0) * (H - B - T)
    g = []
    for i in range(5):
        yv = y0 + i * (y1 - y0) / 4; g.append(f'<line class="a-chart__grid" x1="{L}" x2="{W - Rm}" y1="{Y(yv):.1f}" y2="{Y(yv):.1f}"/><text class="a-chart__axis" x="{L - 6}" y="{Y(yv) + 4:.1f}" text-anchor="end">{yv:.3f}</text>')
        xv = x0 + i * (x1 - x0) / 4; g.append(f'<text class="a-chart__axis" x="{X(xv):.1f}" y="{H - B + 16}" text-anchor="middle">{xfmt(xv)}</text>')
    g.append(f'<text class="a-chart__axis" x="{(L + W - Rm) / 2}" y="{H - 6}" text-anchor="middle">{xlab}</text>')
    g.append(f'<text class="a-chart__axis" x="12" y="{(T + H - B) / 2}" text-anchor="middle" transform="rotate(-90 14 {(T + H - B) / 2})">val quality</text>')
    path = " ".join(f"{'M' if i == 0 else 'L'}{X(x):.1f},{Y(y):.1f}" for i, (k, x, y) in enumerate(pts[:3]))
    g.append(f'<path d="{path}" fill="none" stroke="currentColor" stroke-opacity=".35" stroke-dasharray="4 3"/>')
    for i, (k, x, y) in enumerate(pts):
        lab = {"v0": "v0 (baseline)", "c1": "c1", "c2": "c2 (best)", "c3": "c3", "c4": "c4"}[k]
        g.append(f'<circle class="a-chart__point a-series-{i + 1}" cx="{X(x):.1f}" cy="{Y(y):.1f}" r="7" tabindex="0" data-a-tip-title="{lab}" data-a-tip="quality {y:.3f} · {xlab} {xfmt(x)}"/>'
                 + (f'<text class="a-chart__axis" x="{X(x) - 10:.1f}" y="{Y(y) - 9:.1f}" text-anchor="end" style="font-weight:600">{lab}</text>' if X(x) > W * 0.7 else f'<text class="a-chart__axis" x="{X(x) + 10:.1f}" y="{Y(y) - 9:.1f}" style="font-weight:600">{lab}</text>'))
    rows = "".join(f'<tr><th scope="row">{k}</th><td data-numeric>{xfmt(x)}</td><td data-numeric>{y:.3f}</td></tr>' for k, x, y in pts)
    n = f'<p class="a-section__note">{note}</p>' if note else ""
    return (f'<figure class="a-panel"><figcaption class="a-panel__title">{title}</figcaption>'
            f'<svg class="a-chart" style="font-size:11px;width:100%;height:auto" viewBox="0 0 {W} {H}" role="img" aria-label="{title}">{"".join(g)}</svg>'
            f'<details class="a-disclosure"><summary>Data table</summary><div class="a-table-scroll"><table class="a-table"><caption class="a-visually-hidden">{title}</caption>'
            f'<thead><tr><th scope="col">Version</th><th scope="col" data-numeric>{xlab}</th><th scope="col" data-numeric>val quality</th></tr></thead><tbody>{rows}</tbody></table></div></details>{n}</figure>')

VIZ_SC_COST = _scatter("Val quality vs cost per run", "cost", "$ per run", lambda v: f"${v:.3f}",
                       note="Up-left is better. v0 → c1 → c2 (dashed) moves up and left: higher quality at lower cost per run. Cost comes from the Hidden Layer usage ledger; why the longer prompt costs less per run (e.g. prompt-cache hits) has not been checked.")
VIZ_SC_TURNS = _scatter("Val quality vs turns per run", "turns", "turns per run", lambda v: f"{v:.1f}",
                        note="c2 reaches its quality with slightly fewer turns than v0; c3 uses ~40% more turns and scores lower than c2.")
VIZ_LEN = _fig("line", "Instruction length vs answer length (k characters)", ["Version", "instruction", "answer (mean on val)"],
               [[k, f"{len(TXT[k]) / 1000:.1f}", f"{_ST[k]['anslen'] / 1000:.1f}"] for k in _KS], h=260,
               note="The instruction grows ~90× (0.3k → 25.6k); answers grow once, ~1.8× from v0 to c1 (4.5k → 8.0k), then stay flat. The extra instruction text after c1 does not make answers longer.")

def _ltypes(t):
    out = []
    for ty, s in _sections(t): out += [ty] * len(s.split("\n"))
    return out
def _step(a, b):
    A, B = a.split("\n"), b.split("\n"); ty = _ltypes(b); sm = _dl.SequenceMatcher(a=A, b=B, autojunk=False)
    out, add = [], {"general": 0, "repo": 0}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        for j in range(j1, j2):
            x = B[j]
            if tag == "equal": out.append(_E(x))
            else:
                t = ty[j] if j < len(ty) else "general"; add[t] += len(x) + 1
                out.append(f'<ins style="{_O if t == "repo" else _G}">{_E(x)}</ins>')
    heads = [(h, ty[j]) for j, h in enumerate(B) if h.startswith(("## ", "### ")) and h not in A]
    return f'<pre class="a-prose" style="{_BOX}">' + "\n".join(out) + "</pre>", add, heads
def _stepblock(pa, ch, pid, cid, title):
    html, add, heads = _step(TXT[pa], TXT[ch])
    hl = "".join(f'<li><ins style="{_O if t == "repo" else _G}">{_E(h.lstrip("# "))}</ins></li>' for h, t in heads)
    return f"""
  <h4 class="a-section__title" style="margin-top:18px">{title}</h4>
  <p class="a-prose">{len(TXT[pa]):,} → {len(TXT[ch]):,} chars. New text: <ins style="{_G}">{add['general']/1000:.1f}k general strategy</ins>, <ins style="{_O}">{add['repo']/1000:.1f}k train-repo facts</ins>. New section headings:</p>
  <ul class="a-prose" style="columns:2;margin-top:0">{hl}</ul>
  <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.4fr);gap:16px;align-items:start">
    <div class="a-panel"><div class="a-panel__head"><h4 class="a-panel__title">{pa} — parent <code>{pid}</code></h4></div><pre class="a-prose" style="{_BOX}">{_E(TXT[pa])}</pre></div>
    <div class="a-panel"><div class="a-panel__head"><h4 class="a-panel__title">{ch} — child <code>{cid}</code> (highlighted = new)</h4></div>{html}</div>
  </div>"""
_cards = "".join(
    f'<div class="a-panel" style="padding:10px 12px"><div style="font-weight:700">{k}{" (baseline)" if k == "v0" else ""}</div>'
    f'<div>{len(TXT[k]):,} chars · val {_ST[k]["q"]:.3f}</div>'
    f'<div style="height:10px;display:flex;margin-top:6px;border-radius:3px;overflow:hidden;width:{max(2, len(TXT[k]) / len(TXT["c2"]) * 100):.0f}%">'
    f'<span style="flex:{_comp(TXT[k])[0]};{_G}"></span><span style="flex:{_comp(TXT[k])[1]};{_O}"></span></div></div>'
    + ('<div style="align-self:center;font-size:20px">→</div>' if k != "c2" else "") for k in ("v0", "c1", "c2"))
VIZ_DIFF = f"""
  <div style="display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:10px;margin-top:8px">{_cards}</div>
  <p class="a-section__note">Bar width = instruction length relative to c2; <ins style="{_G}">green</ins> = general answering strategy, <ins style="{_O}">orange</ins> = facts about the two train repositories (pint, responses) taken from judge feedback / reference answers.</p>
{_stepblock("v0", "c1", "001a4209", "5605704e", "Step 1 — v0 → c1 (first accepted reflection)")}
{_stepblock("c1", "c2", "5605704e", "3120b6f2", "Step 2 — c1 → c2 (second accepted reflection)")}
  <p class="a-section__note">Line-level diff; unchanged lines are plain. Scroll inside each panel for the full text.</p>"""
