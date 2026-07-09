"""Greenhouse — per-company public board JSON. No key required."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import Job
from .base import get_json, strip_html

API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


class GreenhouseSource:
    name = "greenhouse"

    def fetch(self, slugs: list[str]) -> list[Job]:
        jobs: list[Job] = []
        for slug in slugs:
            try:
                data = get_json(API.format(slug=slug))
            except Exception as e:  # noqa: BLE001
                print(f"  [greenhouse:{slug}] error: {e}")
                continue
            for j in data.get("jobs", []):
                loc = (j.get("location") or {}).get("name", "")
                jobs.append(Job(
                    title=j.get("title", ""),
                    company=slug,
                    url=j.get("absolute_url", ""),
                    source=f"{self.name}:{slug}",
                    location=loc,
                    description=strip_html(j.get("content")),
                    posted_at=_parse(j.get("updated_at")),
                    remote="remote" in loc.lower(),
                ))
        return jobs


def _parse(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
