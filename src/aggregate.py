"""Pull from all sources, filter by recency, and dedupe."""
from __future__ import annotations

from datetime import datetime, timezone

from .config import all_keywords, load_companies
from .models import Job
from .sources import GreenhouseSource, LeverSource, RemoteOKSource, RemotiveSource


def aggregate(profile: dict, since_days: int = 7, search: str = "flutter") -> list[Job]:
    keywords = all_keywords(profile)
    companies = load_companies()
    raw: list[Job] = []

    print("Fetching sources...")
    raw += RemotiveSource().fetch(search=search)
    raw += RemoteOKSource().fetch(keywords=keywords)
    if companies.get("greenhouse"):
        raw += GreenhouseSource().fetch(companies["greenhouse"])
    if companies.get("lever"):
        raw += LeverSource().fetch(companies["lever"])
    # Ashby adapter is a TODO — the API shape is per-org; add when you pick targets.

    print(f"  {len(raw)} raw postings")

    now = datetime.now(timezone.utc)
    fresh = [j for j in raw if _recent(j, now, since_days)]

    deduped: dict[str, Job] = {}
    for j in fresh:
        if not j.title or not j.url:
            continue
        deduped.setdefault(j.key, j)

    print(f"  {len(deduped)} after recency + dedupe")
    return list(deduped.values())


def _recent(job: Job, now: datetime, since_days: int) -> bool:
    age = job.age_days(now)
    return True if age is None else age <= since_days
