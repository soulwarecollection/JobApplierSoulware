"""Lever — per-company public postings JSON. No key required."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import Job
from .base import get_json, strip_html

API = "https://api.lever.co/v0/postings/{slug}?mode=json"


class LeverSource:
    name = "lever"

    def fetch(self, slugs: list[str]) -> list[Job]:
        jobs: list[Job] = []
        for slug in slugs:
            try:
                data = get_json(API.format(slug=slug))
            except Exception as e:  # noqa: BLE001
                print(f"  [lever:{slug}] error: {e}")
                continue
            for j in data:
                cats = j.get("categories", {}) or {}
                loc = cats.get("location", "") or ""
                jobs.append(Job(
                    title=j.get("text", ""),
                    company=slug,
                    url=j.get("hostedUrl", ""),
                    source=f"{self.name}:{slug}",
                    location=loc,
                    description=strip_html(j.get("descriptionPlain") or j.get("description")),
                    posted_at=_parse_ms(j.get("createdAt")),
                    remote="remote" in (loc + " " + (cats.get("commitment", "") or "")).lower(),
                ))
        return jobs


def _parse_ms(ms: int | None) -> datetime | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (ValueError, TypeError):
        return None
