"""Export the experiment tables from an HL instance DB to data/db/*.jsonl.gz.

Only experiment data is exported: automations (webhook_secret dropped),
automation_instruction_versions, improve_runs. Integration rows, secrets and
chat history are never exported.

    HL_PG_DBNAME=hl_improve python env/export_db.py
"""

import gzip
import json
import os
import pathlib

import psycopg

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "db"
TABLES = {
    "automations": "select id, title, goal, enabled, created, updated, triggers, rate_limit, model from automations",
    "automation_instruction_versions": "select * from automation_instruction_versions order by created",
    "improve_runs": "select * from improve_runs order by created",
}


def main() -> None:
    conn = psycopg.connect(
        host=os.environ.get("HL_PG_HOST", "localhost"),
        port=int(os.environ.get("HL_PG_PORT", "5433")),
        dbname=os.environ.get("HL_PG_DBNAME", "hl_improve"),
        user=os.environ.get("HL_PG_USER", "hl"),
        password=os.environ.get("HL_PG_PASSWORD", "hl"),
    )
    OUT.mkdir(parents=True, exist_ok=True)
    for name, sql in TABLES.items():
        cur = conn.execute(sql)
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()
        with gzip.open(OUT / f"{name}.jsonl.gz", "wt") as f:
            for r in rows:
                f.write(json.dumps(dict(zip(cols, r)), default=str, ensure_ascii=False) + "\n")
        print(name, len(rows))


if __name__ == "__main__":
    main()
