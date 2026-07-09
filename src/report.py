"""Phase 4 — status dashboard + follow-up reminders.

Reads the persistent tracker and prints (and writes) a digest: the funnel by
status, top fresh matches still to action, and follow-ups that are now due.

    python -m src.report
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from .config import ROOT
from .tracker import due_followups, status_counts

TRACKER = ROOT / "output" / "tracker.csv"
FUNNEL = ["new", "queued", "applied", "interview", "closed"]


def build_report(tracker: Path) -> str:
    counts = status_counts(tracker)
    rows = list(csv.DictReader(open(tracker, newline=""))) if tracker.exists() else []
    today = date.today()

    lines = [f"# Job-search digest — {today.isoformat()}", ""]

    # Funnel
    lines.append("## Funnel")
    total = sum(counts.values())
    for s in FUNNEL:
        if counts.get(s):
            bar = "█" * counts[s]
            lines.append(f"- **{s:9}** {counts[s]:3}  {bar}")
    for s, n in counts.items():  # any non-standard statuses
        if s not in FUNNEL:
            lines.append(f"- **{s:9}** {n:3}")
    lines.append(f"\n_{total} jobs tracked._")

    # Due follow-ups
    due = due_followups(tracker, today)
    lines.append(f"\n## ⏰ Follow-ups due ({len(due)})")
    if due:
        for r in sorted(due, key=lambda r: r.get("follow_up", "")):
            lines.append(f"- **{r['follow_up']}** {r['title']} @ {r['company']} — {r['url']}")
    else:
        lines.append("- (none due)")

    # Fresh matches still to action
    todo = [r for r in rows if r.get("status") in ("new", "queued")]
    todo.sort(key=lambda r: int(r.get("score") or 0), reverse=True)
    lines.append(f"\n## Top matches to action ({len(todo)})")
    for r in todo[:15]:
        kit = "📄" if r.get("resume_version") else "  "
        lines.append(f"- {kit} **{r.get('score','?')}/10** {r['title']} @ {r['company']}"
                     f" [{r.get('status')}] — {r['url']}")

    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Status dashboard + follow-up reminders.")
    ap.add_argument("--tracker", default=str(TRACKER))
    args = ap.parse_args()
    tracker = Path(args.tracker)
    if not tracker.exists():
        print("No tracker yet. Run `python -m src.run ...` first.")
        return

    report = build_report(tracker)
    out = ROOT / "output" / f"DIGEST-{date.today().isoformat()}.md"
    out.write_text(report)
    print(report)
    print(f"(saved to {out.relative_to(ROOT)})")


if __name__ == "__main__":
    main()
