"""RemoteOK — free public JSON API. Returns all jobs; we filter client-side."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import Job
from .base import get_json, strip_html

API = "https://remoteok.com/api"


class RemoteOKSource:
    name = "remoteok"

    def fetch(self, keywords: list[str], limit: int = 60) -> list[Job]:
        try:
            data = get_json(API)
        except Exception as e:  # noqa: BLE001
            print(f"  [remoteok] error: {e}")
            return []
        kw = [k.lower() for k in keywords]
        jobs: list[Job] = []
        for j in data:
            if not isinstance(j, dict) or "position" not in j:
                continue  # first element is legal metadata
            hay = f"{j.get('position','')} {' '.join(j.get('tags',[]) or [])}".lower()
            if not any(k in hay for k in kw):
                continue
            jobs.append(Job(
                title=j.get("position", ""),
                company=j.get("company", ""),
                url=j.get("url") or j.get("apply_url", ""),
                source=self.name,
                location=j.get("location", "") or "Remote",
                description=strip_html(j.get("description")),
                posted_at=_parse(j.get("date")),
                remote=True,
                salary=_salary(j),
                tags=j.get("tags", []) or [],
            ))
            if len(jobs) >= limit:
                break
        return jobs


def _salary(j: dict) -> str:
    lo, hi = j.get("salary_min"), j.get("salary_max")
    return f"${lo:,}-${hi:,}" if lo and hi else ""


def _parse(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None
