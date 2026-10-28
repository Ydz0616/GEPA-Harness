"""C2 data generator: expense report (employee submissions) vs ledger (finance system).
Deterministic per seed. Plants 3-8 discrepancies of 4 kinds; writes CSVs + gold.json.
Usage: python gen.py <seed> <outdir>
"""
import csv, json, random, sys
from pathlib import Path

CATS = ["travel", "meals", "software", "office", "training"]
EMP = ["E101", "E102", "E103", "E104", "E105", "E106"]

def main(seed: int, out: Path):
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    n = rng.randint(40, 60)
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "expense_id": f"EXP-{seed:03d}-{i:03d}",
            "employee": rng.choice(EMP),
            "date": f"2026-09-{rng.randint(1, 30):02d}",
            "category": rng.choice(CATS),
            "amount": round(rng.uniform(8, 900), 2),
        })
    report = [dict(r) for r in rows]
    ledger = [dict(r) for r in rows]
    gold = {"mismatches": []}
    k = rng.randint(3, 8)
    kinds = ["amount_diff", "missing_in_ledger", "missing_in_report", "category_diff"]
    picked = rng.sample(range(n), k)
    for idx in picked:
        kind = rng.choice(kinds)
        eid = rows[idx]["expense_id"]
        if kind == "amount_diff":
            delta = round(rng.choice([-1, 1]) * rng.uniform(0.5, 120), 2)
            ledger[idx]["amount"] = round(ledger[idx]["amount"] + delta, 2)
        elif kind == "missing_in_ledger":
            ledger[idx] = None
        elif kind == "missing_in_report":
            report[idx] = None
        else:
            ledger[idx]["category"] = rng.choice([c for c in CATS if c != rows[idx]["category"]])
        gold["mismatches"].append({"expense_id": eid, "kind": kind})
    report = [r for r in report if r]
    ledger = [r for r in ledger if r]
    rng.shuffle(ledger)
    for name, data in (("expense_report.csv", report), ("ledger.csv", ledger)):
        with open(out / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(data)
    gold["report_total"] = round(sum(r["amount"] for r in report), 2)
    gold["ledger_total"] = round(sum(r["amount"] for r in ledger), 2)
    gold["mismatch_ids"] = sorted(m["expense_id"] for m in gold["mismatches"])
    (out / "gold.json").write_text(json.dumps(gold, indent=2))
    print(f"seed={seed} rows={n} mismatches={k} report_total={gold['report_total']} ledger_total={gold['ledger_total']}")

if __name__ == "__main__":
    main(int(sys.argv[1]), Path(sys.argv[2]))
