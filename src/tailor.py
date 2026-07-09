"""Phase 2 — per-job tailoring engine.

Takes a scored Job + your master docs and produces an ATS-clean tailored resume
and cover letter that mirror the job's language — WITHOUT inventing experience.
Writes each result as a self-contained application kit on disk.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from .config import DEFAULT_MODEL, ROOT, all_keywords, matched_keywords
from .models import Job

PROFILE_DIR = ROOT / "profile"
MASTER_RESUME = PROFILE_DIR / "master-resume-ats.md"
COVER_TEMPLATE = PROFILE_DIR / "cover-letter-template.md"


class TailoredApplication(BaseModel):
    resume_markdown: str = Field(description="Full tailored ATS-clean resume in Markdown.")
    cover_letter_markdown: str = Field(description="Full tailored cover letter in Markdown.")
    keywords_matched: list[str] = Field(description="JD keywords the candidate genuinely has, mirrored into the resume.")
    keywords_missing: list[str] = Field(description="JD requirements the candidate does NOT have (be honest).")
    tailoring_notes: list[str] = Field(description="What was emphasized/reordered and why (max 5).")
    ats_fit_estimate: int = Field(ge=1, le=10, description="Estimated ATS keyword match, 1-10.")


_SYSTEM = """You are an expert resume writer tailoring ONE candidate's application to ONE job.

ABSOLUTE RULES:
- NEVER invent employers, job titles, dates, metrics, certifications, or skills. Use only facts
  present in the candidate's master resume. You may rephrase, reorder, and re-emphasize.
- Mirror the job description's exact terminology ONLY where the candidate genuinely has that
  experience (e.g. if the JD says "GraphQL" and the master shows GraphQL, use "GraphQL").
- Keep the resume ATS-clean: single column, standard section headings, no tables/columns/photos.
- Reorder "Selected Projects" and emphasize bullets so the most JD-relevant work comes first.
- Keep the resume to ~2 pages of content. Keep the cover letter ~250-300 words.
- Fill every {{variable}} in the cover-letter template; remove any that don't apply.
- Be honest in keywords_missing — list real gaps so the candidate knows them before applying."""


def load_master_docs() -> tuple[str, str]:
    return MASTER_RESUME.read_text(), COVER_TEMPLATE.read_text()


def tailor_one(client, job: Job, profile: dict, master_resume: str,
               cover_template: str, model: str | None = None) -> TailoredApplication:
    model = model or DEFAULT_MODEL
    prompt = (
        f"MASTER RESUME (source of truth — do not exceed these facts):\n{master_resume}\n\n"
        f"COVER LETTER TEMPLATE (fill the variables):\n{cover_template}\n\n"
        f"CANDIDATE PREFERENCES:\n{json.dumps(profile.get('preferences', {}))}\n\n"
        f"TARGET JOB:\nTitle: {job.title}\nCompany: {job.company}\nLocation: {job.location}\n"
        f"Description:\n{job.description[:3800]}\n\n"
        f"Produce the tailored resume and cover letter for THIS job."
    )
    resp = client.messages.parse(
        model=model,
        max_tokens=6000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_format=TailoredApplication,
    )
    return resp.parsed_output


def write_kit(job: Job, tailored: TailoredApplication, base_dir: Path | None = None) -> str:
    """Write resume + cover letter + match notes to disk. Returns the version id."""
    base_dir = base_dir or (ROOT / "output" / "applications" / date.today().isoformat())
    version = f"{_slug(job.company)}-{_slug(job.title)}-{job.key[:6]}"
    folder = base_dir / version
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "resume.md").write_text(tailored.resume_markdown)
    (folder / "cover-letter.md").write_text(tailored.cover_letter_markdown)
    (folder / "MATCH.md").write_text(
        f"# Application kit — {job.title} @ {job.company}\n\n"
        f"- **Job:** {job.url}\n"
        f"- **ATS fit estimate:** {tailored.ats_fit_estimate}/10\n\n"
        f"## Keywords matched\n" + _bullets(tailored.keywords_matched) +
        f"\n## Gaps to be aware of\n" + _bullets(tailored.keywords_missing) +
        f"\n## Tailoring notes\n" + _bullets(tailored.tailoring_notes)
    )
    return version


def tailor_and_write(client, jobs: list[Job], profile: dict,
                     model: str | None = None) -> dict[str, str]:
    """Tailor a list of jobs; return {job.url: version_id} for the tracker."""
    master_resume, cover_template = load_master_docs()
    out: dict[str, str] = {}
    for i, job in enumerate(jobs, 1):
        try:
            tailored = tailor_one(client, job, profile, master_resume, cover_template, model)
            version = write_kit(job, tailored)
        except Exception as e:  # noqa: BLE001
            print(f"  [tailor {i}/{len(jobs)}] error on {job.title!r}: {e}")
            continue
        out[job.url] = version
        print(f"  [tailor {i}/{len(jobs)}] kit ready: {version} (ATS ~{tailored.ats_fit_estimate}/10)")
    return out


# ---------------------------------------------------------------------------
# Offline / mechanical tailoring (no LLM, no key). Fills the cover template and
# computes a real keyword-gap report; the resume stays your master verbatim.
# ---------------------------------------------------------------------------

# Common tech terms we can detect as "in the JD but not in your profile" = a gap.
SKILL_VOCAB = [
    "flutter", "dart", "react native", "react", "typescript", "javascript", "kotlin",
    "java", "swift", "swiftui", "objective-c", "jetpack compose", "bloc", "provider",
    "riverpod", "redux", "graphql", "rest", "grpc", "firebase", "aws", "gcp", "azure",
    "kubernetes", "docker", "terraform", "ci/cd", "fastlane", "bitrise", "codemagic",
    "github actions", "unit testing", "integration testing", "tdd", "agile", "scrum",
    "python", "go", "rust", "node", "sql", "postgresql", "mongodb", "kafka", "rabbitmq",
    "ml", "machine learning", "llm", "rag", "ffmpeg", "webrtc", "opengl", "ar", "arkit",
    "arcore", "bluetooth", "nfc", "webassembly", "kmm", "kotlin multiplatform",
]


def mechanical_tailor(job: Job, profile: dict, master_resume: str, cover_template: str) -> TailoredApplication:
    kw = set(all_keywords(profile))
    jd = f"{job.title} {job.description}"
    matched = matched_keywords(jd, kw)
    missing = [t for t in matched_keywords(jd, SKILL_VOCAB) if t not in kw]
    cover = _fill_cover(cover_template, job)
    ats = max(1, min(10, 4 + min(6, len(matched) // 2)))
    notes = [
        "Mechanical tailoring (offline): resume is your master, unchanged.",
        "Review MATCH.md for keyword gaps and edit the [FILL: …] spots in the cover letter.",
    ]
    return TailoredApplication(
        resume_markdown=master_resume,
        cover_letter_markdown=cover,
        keywords_matched=matched[:20],
        keywords_missing=missing[:15],
        tailoring_notes=notes,
        ats_fit_estimate=ats,
    )


def tailor_and_write_heuristic(jobs: list[Job], profile: dict) -> dict[str, str]:
    master_resume, cover_template = load_master_docs()
    out: dict[str, str] = {}
    for i, job in enumerate(jobs, 1):
        tailored = mechanical_tailor(job, profile, master_resume, cover_template)
        version = write_kit(job, tailored)
        out[job.url] = version
        print(f"  [tailor {i}/{len(jobs)}] kit ready: {version} "
              f"(matched {len(tailored.keywords_matched)} kw, {len(tailored.keywords_missing)} gaps)")
    return out


def _fill_cover(template: str, job: Job) -> str:
    filled = (template
              .replace("{{job_title}}", job.title)
              .replace("{{company}}", job.company)
              .replace("{{hiring_manager_or_team}}", "Hiring Team"))
    # Any remaining {{placeholders}} need a human decision — mark them clearly.
    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", r"[FILL: \1]", filled)


def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:40]


def _bullets(items: list[str]) -> str:
    return "".join(f"- {x}\n" for x in items) or "- (none)\n"
