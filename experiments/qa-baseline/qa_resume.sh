#!/bin/bash
# Resume the qa v0 baseline: top every val/heldout example up to 3 done runs.
cd /home/ubuntu/repos/Hidden-Layer-Internal
ENVV="HL_IMPROVE_JUDGE_LOG=/home/ubuntu/improve-runs/qa-judge-calls.jsonl HL_PG_DBNAME=hl_improve HL_TENANT_ID=devinlive HL_MEMORY_BACKEND=off"
plan=$(env $ENVV .venv/bin/python - <<'PY' 2>/dev/null | grep '^K'
import json
from hidden_layer.config import Settings; from hidden_layer import db
ex=[json.loads(l) for l in open("src/hidden_layer/improve/bench/qa/examples.jsonl") if l.strip()]
with db.pg_pool(Settings()).connection() as c:
    done={r['example_id']:r['n'] for r in c.execute("select example_id, count(*) n from improve_runs where instruction_version_id='001a42091bad' and status='done' group by 1").fetchall()}
need={}
for e in ex:
    if e['split'] in ('val','heldout'):
        k=max(0,3-done.get(e['id'],0))
        if k: need.setdefault(k,[]).append(e['id'])
for k,ids in need.items(): print(f"K{k} {','.join(ids)}")
PY
)
echo "$plan"
echo "$plan" | while read k ids; do
  env $ENVV .venv/bin/hl improve run qa --automation 6550dcc0ce9f --version 001a42091bad --only "$ids" -k ${k#K} -c 3 >> /tmp/improve-qa-base-resume.log 2>&1
done
echo RESUME_EXIT=$? >> /tmp/improve-qa-base-resume.log
