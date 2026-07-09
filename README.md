# JobApplierSoulware

A semi-autonomous job-search co-pilot: it finds relevant remote roles from legal job
APIs, scores them against your profile, tailors an ATS-clean resume + cover letter per
job, and keeps a human on the submit button. No LinkedIn/Indeed scraping, no auto-submit,
no account-ban risk.

## Pipeline
```
sources → prefilter → score → tailor → apply-queue → tracker
```

## Two engines (score + tailor)
| Engine | Needs a key? | Quality |
|---|---|---|
| `heuristic` | No — free, offline | Keyword overlap + mechanical tailoring |
| `llm` | Yes (`ANTHROPIC_API_KEY`) | Semantic scoring + real per-job rewrites |

`--engine auto` (default) uses `llm` if a key is set, else `heuristic`.

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp profile/master-profile.example.yaml profile/master-profile.yaml   # then fill it in
cp .env.example .env                                                  # optional: ANTHROPIC_API_KEY

# Fully offline (no key):
python -m src.run --engine heuristic --since-days 7 --min-score 6 --tailor
python -m src.apply_queue
python -m src.report
```

## Privacy
`profile/master-profile.yaml`, your tailored `output/`, and `.env` are **gitignored** —
your personal data stays local and out of this (public) repo. Only the example profile
and code are committed.
