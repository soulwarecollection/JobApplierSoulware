"""Score each job 1-10 against the profile using Claude (structured output)."""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from .config import DEFAULT_MODEL
from .models import Job


class JobScore(BaseModel):
    score: int = Field(ge=1, le=10, description="Overall fit, 1-10")
    recommendation: str = Field(description="One of: Apply, Consider, Pass")
    remote_ok: bool = Field(description="Is this genuinely remote / open to the candidate's region?")
    visa_concern: bool = Field(description="Does it require existing work auth with no sponsorship?")
    fit_reasons: list[str] = Field(description="Why this matches the candidate (max 3)")
    gaps: list[str] = Field(description="Where the candidate falls short (max 3)")
    one_line: str = Field(description="One-sentence verdict")


_SYSTEM = """You are a seasoned senior technical recruiter screening roles for ONE candidate.
Score how well each job fits THIS candidate. A hard blocker (junior title, onsite-only with no
remote, requires existing work authorization the candidate lacks with no sponsorship) caps the
score at 4. Be honest and concise — the candidate uses this to decide where to spend effort."""


def _candidate_brief(profile: dict) -> str:
    idn = profile.get("identity", {})
    prefs = profile.get("preferences", {})
    return json.dumps({
        "headline": idn.get("headline"),
        "summary": profile.get("summary"),
        "target_roles": profile.get("target_roles"),
        "key_skills": profile.get("skills"),
        "preferences": prefs,
        "blockers": profile.get("blockers"),
    }, indent=2)[:6000]


def score_jobs(jobs: list[Job], profile: dict, model: str | None = None) -> list[tuple[Job, JobScore]]:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    model = model or DEFAULT_MODEL
    brief = _candidate_brief(profile)
    results: list[tuple[Job, JobScore]] = []

    for i, job in enumerate(jobs, 1):
        prompt = (
            f"CANDIDATE PROFILE:\n{brief}\n\n"
            f"JOB POSTING:\n"
            f"Title: {job.title}\nCompany: {job.company}\nLocation: {job.location}\n"
            f"Remote (source flag): {job.remote}\nSalary: {job.salary or 'n/a'}\n"
            f"Description:\n{job.description[:3500]}\n\n"
            f"Score this job for the candidate."
        )
        try:
            resp = client.messages.parse(
                model=model,
                max_tokens=1200,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                output_format=JobScore,
            )
            results.append((job, resp.parsed_output))
        except Exception as e:  # noqa: BLE001
            print(f"  [score {i}/{len(jobs)}] error on {job.title!r}: {e}")
        else:
            print(f"  [score {i}/{len(jobs)}] {resp.parsed_output.score}/10 {job.title} @ {job.company}")

    results.sort(key=lambda r: r[1].score, reverse=True)
    return results
