"""Load data/db/*.jsonl.gz into a freshly migrated HL database (after `hl db-upgrade`).

Restores the three experiment automations, all instruction versions (v0 + GEPA
candidates) and every improve_runs row, so `hl improve report` and
`hl improve optimize --reuse-seed-runs` see the earlier runs. A new random
webhook_secret is generated per automation (the originals are not published).
Idempotent: existing ids are skipped.

    HL_PG_DBNAME=hl_improve python env/restore_db.py
"""

import gzip
import json
import os
import pathlib
import secrets

import psycopg

DATA = pathlib.Path(__file__).resolve().parent.parent / "data" / "db"


def rows(name: str) -> list[dict]:
    with gzip.open(DATA / f"{name}.jsonl.gz", "rt") as f:
        return [json.loads(line) for line in f if line.strip()]


def insert(conn: psycopg.Connection, table: str, row: dict) -> int:
    cols = list(row)
    sql = (
        f"insert into {table} ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))}) "
        "on conflict (id) do nothing"
    )
    return conn.execute(sql, [row[c] for c in cols]).rowcount


def main() -> None:
    conn = psycopg.connect(
        host=os.environ.get("HL_PG_HOST", "localhost"),
        port=int(os.environ.get("HL_PG_PORT", "5433")),
        dbname=os.environ.get("HL_PG_DBNAME", "hl_improve"),
        user=os.environ.get("HL_PG_USER", "hl"),
        password=os.environ.get("HL_PG_PASSWORD", "hl"),
        autocommit=False,
    )
    with conn:
        conn.execute(
            "insert into person (id, role) values ('anonymous', 'owner') on conflict (id) do nothing"
        )
        n = {"automations": 0, "automation_instruction_versions": 0, "improve_runs": 0}
        for a in rows("automations"):
            a.update(chat_id="", person_id="anonymous", created_by="anonymous",
                     webhook_secret=secrets.token_urlsafe(32), webhook_filter="")
            n["automations"] += insert(conn, "automations", a)
        for v in rows("automation_instruction_versions"):
            n["automation_instruction_versions"] += insert(conn, "automation_instruction_versions", v)
        for r in rows("improve_runs"):
            n["improve_runs"] += insert(conn, "improve_runs", r)
    print("inserted", n)


if __name__ == "__main__":
    main()
