"""Offline scorer — ranks jobs by keyword overlap with the profile. No LLM, no key.

Produces the same fields the tracker/CLI read (score, recommendation, remote_ok,
visa_concern, one_line), so it's a drop-in replacement for the Claude scorer.
Lower fidelity than the LLM, but free and instant.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import all_keywords, all_target_titles, matched_keywords
from .models import Job
from .prefilter import NEGATIVE

CORE = ["flutter", "dart", "mobile", "react native", "ios", "android",
        "bloc", "swift", "kotlin"]

# Titles that clearly aren't this candidate's lane, regardless of keyword overlap.
NON_ENGINEERING = ["product manager", "project manager", "program manager", "designer",
                   "ux researcher", "sales", "account executive", "recruiter", "marketing",
                   "customer success", "data scientist", "data analyst", "content writer"]

_VISA_PHRASES = ["no visa sponsorship", "not able to sponsor", "cannot sponsor",
                 "must be authorized to work", "authorized to work in", "no sponsorship",
                 "requires work authorization", "without sponsorship", "citizens only",
                 "must be located in", "must reside in"]
_REMOTE_WORDS = ["remote", "worldwide", "anywhere", "global"]


@dataclass
class HeuristicScore:
    score: int
    recommendation: str
    remote_ok: bool
    visa_concern: bool
    one_line: str
    fit_reasons: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


def score_jobs_heuristic(jobs: list[Job], profile: dict) -> list[tuple[Job, HeuristicScore]]:
    keywords = all_keywords(profile)
    titles = all_target_titles(profile)
    needs_sponsor = bool(profile.get("preferences", {}).get("needs_sponsorship_for_onsite"))

    results: list[tuple[Job, HeuristicScore]] = []
    for job in jobs:
        title_l = job.title.lower()
        text = f"{title_l}\n{' '.join(job.tags).lower()}\n{job.description.lower()}"
        matched = matched_keywords(text, keywords)
        n = len(matched)
        # Word-boundary title checks so 'bloc' won't match 'block', 'ios' won't match 'kiosk'.
        title_hit = bool(matched_keywords(title_l, titles)) or bool(matched_keywords(title_l, CORE))
        # Is there a real mobile signal, or just generic infra keywords?
        mobile_signal = title_hit or bool(matched_keywords(text, CORE))

        score = 4 + (2 if title_hit else 0) + min(4, n // 2)
        score = max(1, min(10, score))

        # No mobile signal at all -> generic overlap only; don't call it "Apply".
        if not mobile_signal:
            score = min(score, 5)
        if any(neg in title_l for neg in NEGATIVE):
            score = min(score, 3)
        if any(bad in title_l for bad in NON_ENGINEERING):
            score = min(score, 3)

        remote = bool(job.remote) or any(w in (job.location or "").lower() for w in _REMOTE_WORDS)
        visa = needs_sponsor and any(p in text for p in _VISA_PHRASES)
        if visa:
            score = min(score, 5)

        rec = "Apply" if score >= 8 else "Consider" if score >= 6 else "Pass"
        one_line = (f"{n} profile keywords matched"
                    + (f": {', '.join(matched[:6])}" if matched else " (weak match)"))
        results.append((job, HeuristicScore(
            score=score, recommendation=rec, remote_ok=remote, visa_concern=visa,
            one_line=one_line, fit_reasons=matched[:8])))

    results.sort(key=lambda r: r[1].score, reverse=True)
    return results
