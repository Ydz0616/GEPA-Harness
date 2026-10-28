import json, statistics as st, collections
from hidden_layer.config import Settings; from hidden_layer import db
ex={json.loads(l)['id']:json.loads(l) for l in open("src/hidden_layer/improve/bench/qa/examples.jsonl") if l.strip()}
with db.pg_pool(Settings()).connection() as c:
    rows=[dict(r) for r in c.execute("select example_id, split, score, cost_usd, latency_s, turns, tool_calls from improve_runs where instruction_version_id='001a42091bad' and status='done'").fetchall()]
by=collections.defaultdict(list)
for r in rows: by[r['split']].append(r)
for sp,rs in by.items():
    q=[float(r['score']) for r in rs]
    per=collections.defaultdict(list)
    for r in rs: per[r['example_id']].append(float(r['score']))
    print(sp, 'runs',len(rs),'Qs',len(per),'quality',round(st.mean(q),3),'per-Q stdev',round(st.mean(st.pstdev(v) for v in per.values() if len(v)>1),3) if any(len(v)>1 for v in per.values()) else None,
          'cost',round(st.mean(float(r['cost_usd']) for r in rs if r['cost_usd'] is not None),4),'turns',round(st.mean(r['turns'] for r in rs if r['turns'] is not None),1),
          'tools',round(st.mean(r['tool_calls'] for r in rs if r['tool_calls'] is not None),1),'lat med',st.median(float(r['latency_s']) for r in rs if r['latency_s'] is not None),
          'total $',round(sum(float(r['cost_usd'] or 0) for r in rs),2))
    print('  low Qs (<0.8):', sorted((k,round(st.mean(v),2),ex[k]['kind']) for k,v in per.items() if st.mean(v)<0.8))
