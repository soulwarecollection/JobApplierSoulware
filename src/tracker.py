"""Write the ranked results to a CSV tracker (append + dedupe by URL)."""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import Job
from .score import JobScore

COLUMNS = [
    "date_found", "score", "recommendation", "title", "company", "location",
    "remote_ok", "visa_concern", "source", "url", "one_line",
    "resume_version", "status", "follow_up",
]


def write_tracker(rows: list[tuple[Job, JobScore]], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    existing_urls = _existing_urls(out_path)
    today = date.today().isoformat()

    new_rows = []
    for job, sc in rows:
        if job.url in existing_urls:
            continue
        new_rows.append({
            "date_found": today,
            "score": sc.score,
            "recommendation": sc.recommendation,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "remote_ok": sc.remote_ok,
            "visa_concern": sc.visa_concern,
            "source": job.source,
            "url": job.url,
            "one_line": sc.one_line,
            "resume_version": "",   # filled by the tailoring engine (Phase 2)
            "status": "new",        # new -> queued -> applied -> interview -> closed
            "follow_up": "",
        })

    write_header = not out_path.exists()
    with open(out_path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if write_header:
            w.writeheader()
        w.writerows(new_rows)
    return len(new_rows)


def update_resume_version(path: Path, versions: dict[str, str]) -> int:
    """Set the resume_version column for rows whose URL is in `versions`."""
    if not path.exists() or not versions:
        return 0
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    n = 0
    for r in rows:
        v = versions.get(r.get("url", ""))
        if v:
            r["resume_version"] = v
            if r.get("status") == "new":
                r["status"] = "queued"
            n += 1
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return n


def update_status(path: Path, url: str, status: str) -> bool:
    """Flip the status of one row (e.g. queued -> applied)."""
    return _mutate(path, url, lambda r: r.update(status=status))


def mark_applied(path: Path, url: str, follow_up_days: int = 7) -> bool:
    """Flip to 'applied' and stamp a follow-up date `follow_up_days` out."""
    due = (date.today() + timedelta(days=follow_up_days)).isoformat()
    return _mutate(path, url, lambda r: r.update(status="applied", follow_up=due))


def due_followups(path: Path, today: date | None = None) -> list[dict]:
    """Applied rows whose follow-up date is today or earlier."""
    today = today or date.today()
    out = []
    for r in _read(path):
        if r.get("status") != "applied":
            continue
        fu = (r.get("follow_up") or "").strip()
        if fu and _as_date(fu) and _as_date(fu) <= today:
            out.append(r)
    return out


def status_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in _read(path):
        counts[r.get("status") or "new"] = counts.get(r.get("status") or "new", 0) + 1
    return counts


def _mutate(path: Path, url: str, fn) -> bool:
    if not path.exists():
        return False
    rows = _read(path)
    hit = False
    for r in rows:
        if r.get("url") == url:
            fn(r)
            hit = True
    if hit:
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
    return hit


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _as_date(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _existing_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with open(path, newline="") as f:
        return {r["url"] for r in csv.DictReader(f) if r.get("url")}
