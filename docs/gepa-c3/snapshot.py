"""C3 gold snapshot: issues opened + non-bot PRs merged in a window of a repo.
Usage: python snapshot.py owner/repo 2026-09-14 2026-09-21 out.json   (start inclusive, end exclusive, UTC)
Gold is frozen the moment this runs; evaluator never re-queries GitHub.
"""
import json, subprocess, sys

def gh(path):
    return json.loads(subprocess.check_output(["gh", "api", "--paginate", "-X", "GET", path]))

def main(repo, start, end, out):
    items = gh(f"repos/{repo}/issues?state=all&since={start}T00:00:00Z&per_page=100")
    issues = [i for i in items if "pull_request" not in i and start <= i["created_at"][:10] < end]
    prs = gh(f"repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100")
    merged = [p for p in prs if p.get("merged_at") and start <= p["merged_at"][:10] < end
              and not p["user"]["login"].endswith("[bot]")]
    gold = {
        "repo": repo, "window": [start, end],
        "issues_opened": sorted([{"number": i["number"], "labels": sorted(l["name"] for l in i["labels"]),
                                  "title": i["title"]} for i in issues], key=lambda x: x["number"]),
        "prs_merged": sorted([{"number": p["number"], "author": p["user"]["login"], "title": p["title"]}
                              for p in merged], key=lambda x: x["number"]),
    }
    gold["issue_numbers"] = [i["number"] for i in gold["issues_opened"]]
    gold["pr_numbers"] = [p["number"] for p in gold["prs_merged"]]
    import os; os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump(gold, open(out, "w"), indent=2)
    print(f"{repo} {start}..{end}: issues_opened={len(issues)} prs_merged(non-bot)={len(merged)}")

if __name__ == "__main__":
    main(*sys.argv[1:5])
