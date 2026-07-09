"""Remotive — free public JSON API, remote-only jobs. No key required."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import Job
from .base import get_json, strip_html

API = "https://remotive.com/api/remote-jobs"


class RemotiveSource:
    name = "remotive"

    def fetch(self, search: str, limit: int = 50) -> list[Job]:
        try:
            data = get_json(API, {"search": search, "limit": limit})
        except Exception as e:  # noqa: BLE001 - one bad source shouldn't kill the run
            print(f"  [remotive] error: {e}")
            return []
        jobs = []
        for j in data.get("jobs", []):
            jobs.append(Job(
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                url=j.get("url", ""),
                source=self.name,
                location=j.get("candidate_required_location", "") or "Remote",
                description=strip_html(j.get("description")),
                posted_at=_parse(j.get("publication_date")),
                remote=True,
                salary=j.get("salary", "") or "",
                tags=j.get("tags", []) or [],
            ))
        return jobs


def _parse(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
