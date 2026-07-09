"""Cheap title/keyword gate so we don't spend LLM tokens on obvious non-fits."""
from __future__ import annotations

from .config import all_keywords, all_target_titles
from .models import Job

# Hard junior/level blockers (profile is Lead/Senior).
NEGATIVE = ["junior", "intern", "internship", "entry level", "entry-level",
            "graduate", "trainee", "apprentice", "working student"]


def prefilter(jobs: list[Job], profile: dict) -> list[Job]:
    titles = all_target_titles(profile)
    keywords = all_keywords(profile)
    # Core stack signals worth matching even if the title is generic.
    core = ["flutter", "dart", "mobile", "react native", "ios", "android",
            "bloc", "swift", "kotlin"]

    kept: list[Job] = []
    for j in jobs:
        t = j.title.lower()
        if any(n in t for n in NEGATIVE):
            continue
        blob = f"{t} {' '.join(j.tags).lower()} {j.description[:600].lower()}"
        title_hit = any(tt in t for tt in titles) or any(c in t for c in core)
        kw_hits = sum(1 for k in keywords if k in blob)
        if title_hit or kw_hits >= 3:
            kept.append(j)
    print(f"  {len(kept)} after prefilter")
    return kept
