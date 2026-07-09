"""Phase 3 — apply queue + alerts (the human-in-the-loop submission aid).

Reads the tracker, and for every job that has a tailored kit (status `queued`)
builds an APPLY.md checklist next to the kit: the job link, the resume/cover
paths, your pre-filled common answers, and a watchlist of judgment questions to
expect. It ALERTS you to any answer you still need to decide before submitting.

    python -m src.apply_queue                       # build the queue
    python -m src.apply_queue --mark-applied <url>  # flip a row to 'applied'
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .config import ROOT, load_profile
from .tracker import mark_applied

APPLICATIONS = ROOT / "output" / "applications"

# Judgment questions the co-pilot can't answer for you — expect these on
# Workday / Greenhouse / Lever / Ashby and have answers ready.
WATCHLIST = [
    "Work authorization for the job's country (and whether you need sponsorship)",
    "Salary / compensation expectations",
    '"Why do you want to work here?" — adapt the cover letter',
    "Notice period / earliest start date",
    "Any role-specific screening questions",
    "EEO / demographic questions (optional)",
]
# Friction points where the tool stops and you take over.
INTERVENE = ["Account creation / login wall", "CAPTCHA", "Resume re-parse / manual field fixes",
             "File upload (use the tailored resume.md exported to PDF)"]

_MISSING = {"", "tbd", "none", None}


def latest_tracker() -> Path | None:
    stable = ROOT / "output" / "tracker.csv"
    if stable.exists():
        return stable
    files = sorted((ROOT / "output").glob("jobs-*.csv"))  # legacy fallback
    return files[-1] if files else None


def find_kit(version: str) -> Path | None:
    matches = list(APPLICATIONS.glob(f"*/{version}"))
    return matches[0] if matches else None


def common_answers(profile: dict) -> tuple[list[str], list[str]]:
    """Return (ready answers, alerts-for-missing)."""
    idn = profile.get("identity", {})
    ans = profile.get("application_answers", {})
    fields = {
        "Full name": idn.get("display_name"),
        "Email": idn.get("email"),
        "Phone": idn.get("phone"),
        "Location": idn.get("location"),
        "LinkedIn": idn.get("links", {}).get("linkedin"),
        "Work authorization": ans.get("work_authorization"),
        "Notice period": ans.get("notice_period"),
        "Salary expectation (USD)": ans.get("salary_expectation_usd"),
        "Willing to relocate": ans.get("willing_to_relocate"),
        "Years experience": ans.get("years_experience"),
        "Years Flutter": ans.get("years_flutter"),
    }
    ready, alerts = [], []
    for label, val in fields.items():
        if str(val).strip().lower() in _MISSING:
            alerts.append(label)
        else:
            ready.append(f"- **{label}:** {val}")
    return ready, alerts


def build_apply_md(row: dict, kit: Path, ready: list[str], alerts: list[str]) -> None:
    visa = " ⚠️ visa/sponsorship flagged" if row.get("visa_concern") == "True" else ""
    lines = [
        f"# Apply: {row['title']} @ {row['company']}",
        f"\n**Score:** {row['score']}/10 ({row['recommendation']}){visa}",
        f"**Job:** {row['url']}",
        f"**Verdict:** {row['one_line']}",
        "\n## Documents (export to PDF before uploading)",
        "- Resume: `resume.md`",
        "- Cover letter: `cover-letter.md`",
        "- Match notes / keyword gaps: `MATCH.md`",
        "\n## Copy-paste answers",
        *ready,
        '\n_"Why this company": pull 1–2 specific lines from `cover-letter.md`._',
    ]
    if alerts:
        lines += ["\n## ⚠️ DECIDE BEFORE SUBMITTING (missing from your profile)",
                  *[f"- {a}" for a in alerts]]
    lines += ["\n## Judgment questions to expect", *[f"- {q}" for q in WATCHLIST],
              "\n## Stop & intervene if you hit", *[f"- {q}" for q in INTERVENE],
              "\n## After submitting", "- [ ] Mark applied: "
              f"`python -m src.apply_queue --mark-applied {row['url']}`",
              "- [ ] Set a follow-up date (~1 week)"]
    (kit / "APPLY.md").write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the apply queue from tailored kits.")
    ap.add_argument("--tracker", help="Path to a jobs-*.csv (default: latest).")
    ap.add_argument("--status", default="queued", help="Which status to queue (default: queued).")
    ap.add_argument("--mark-applied", metavar="URL", help="Flip one row to 'applied' and exit.")
    args = ap.parse_args()

    tracker = Path(args.tracker) if args.tracker else latest_tracker()
    if not tracker or not tracker.exists():
        print("No tracker found. Run `python -m src.run ... --tailor` first.")
        return

    if args.mark_applied:
        ok = mark_applied(tracker, args.mark_applied)
        print("Marked applied (+ follow-up set ~1 week out)." if ok else "URL not found in tracker.")
        return

    profile = load_profile()
    ready, alerts = common_answers(profile)

    with open(tracker, newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if r.get("status") == args.status and r.get("resume_version")]
    rows.sort(key=lambda r: int(r.get("score") or 0), reverse=True)

    index = ["# Apply queue", f"\n{len(rows)} tailored kit(s) ready to submit.\n"]
    if alerts:
        index.append("> ⚠️ Profile gaps apply to EVERY kit — fill these in `master-profile.yaml`: "
                     + ", ".join(alerts) + "\n")

    built = 0
    for r in rows:
        kit = find_kit(r["resume_version"])
        if not kit:
            print(f"  kit folder missing for {r['resume_version']} — re-run --tailor")
            continue
        build_apply_md(r, kit, ready, alerts)
        built += 1
        index.append(f"- [ ] **{r['score']}/10** {r['title']} @ {r['company']} "
                     f"→ `{kit.relative_to(ROOT)}/APPLY.md`")

    (ROOT / "output" / "APPLY-QUEUE.md").write_text("\n".join(index) + "\n")
    print(f"Built {built} APPLY.md checklist(s).")
    print(f"Queue index: output/APPLY-QUEUE.md")
    if alerts:
        print(f"⚠️  {len(alerts)} profile field(s) need a decision before submitting: {', '.join(alerts)}")


if __name__ == "__main__":
    main()
