"""CLI entrypoint: aggregate -> prefilter -> score -> track -> (optionally) tailor.

Two engines for the score+tailor stages:
  llm        — Claude (needs ANTHROPIC_API_KEY). Best quality.
  heuristic  — keyword overlap + mechanical tailoring. No key, no cost.
Default is `auto`: use llm if a key is set, else fall back to heuristic.

    python -m src.run --since-days 7 --min-score 7 --tailor
    python -m src.run --engine heuristic --tailor        # force no-key mode
    python -m src.run --no-llm                            # alias for heuristic
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from .aggregate import aggregate
from .config import ROOT, load_profile
from .prefilter import prefilter
from .tracker import update_resume_version, write_tracker


def resolve_engine(args) -> str:
    if args.no_llm:
        return "heuristic"
    if args.engine != "auto":
        engine = args.engine
    else:
        engine = "llm" if os.getenv("ANTHROPIC_API_KEY") else "heuristic"
    if engine == "llm" and not os.getenv("ANTHROPIC_API_KEY"):
        print("  No ANTHROPIC_API_KEY found — falling back to the heuristic engine.")
        engine = "heuristic"
    return engine


def main() -> None:
    ap = argparse.ArgumentParser(description="Job-application co-pilot — aggregate, score, track.")
    ap.add_argument("--since-days", type=int, default=7, help="Only postings newer than this.")
    ap.add_argument("--search", default="flutter", help="Primary keyword for keyword-search sources.")
    ap.add_argument("--min-score", type=int, default=7, help="Only show/track jobs scoring >= this.")
    ap.add_argument("--limit-score", type=int, default=40, help="Max jobs to send to the LLM (llm engine only).")
    ap.add_argument("--tailor", action="store_true", help="Build tailored resume+cover kits for top matches.")
    ap.add_argument("--tailor-top", type=int, default=10, help="How many top matches to tailor.")
    ap.add_argument("--engine", choices=["auto", "llm", "heuristic"], default="auto",
                    help="Scoring/tailoring engine (default: auto).")
    ap.add_argument("--no-llm", action="store_true", help="Alias for --engine heuristic (no API key).")
    ap.add_argument("--out", default=str(ROOT / "output" / "tracker.csv"),
                    help="Persistent tracker CSV (status carries across runs).")
    args = ap.parse_args()

    engine = resolve_engine(args)
    profile = load_profile()
    jobs = aggregate(profile, since_days=args.since_days, search=args.search)
    jobs = prefilter(jobs, profile)
    print(f"\nEngine: {engine}")

    if engine == "heuristic":
        from .score_heuristic import score_jobs_heuristic
        scored = score_jobs_heuristic(jobs, profile)  # free — score them all
    else:
        from .score import score_jobs  # deferred import so heuristic needs no key
        candidates = jobs[: args.limit_score]
        print(f"Scoring {len(candidates)} jobs with Claude...")
        scored = score_jobs(candidates, profile)

    keep = [(j, s) for j, s in scored if s.score >= args.min_score]
    out_path = Path(args.out)
    added = write_tracker(keep, out_path)

    print(f"\n=== Top matches (>= {args.min_score}/10) ===")
    for job, sc in keep[:25]:
        flag = " ⚠️visa" if sc.visa_concern else ""
        print(f"  {sc.score}/10  {sc.recommendation:8} {job.title} @ {job.company}{flag}")
        print(f"         {sc.one_line}")
        print(f"         {job.url}")
    print(f"\nWrote {added} new rows to {out_path}")

    if args.tailor and keep:
        to_tailor = [j for j, _ in keep][: args.tailor_top]
        print(f"\nTailoring {len(to_tailor)} application kits ({engine})...")
        if engine == "heuristic":
            from .tailor import tailor_and_write_heuristic
            versions = tailor_and_write_heuristic(to_tailor, profile)
        else:
            import anthropic
            from .tailor import tailor_and_write
            versions = tailor_and_write(anthropic.Anthropic(), to_tailor, profile)
        updated = update_resume_version(out_path, versions)
        print(f"Built {len(versions)} kits in output/applications/; linked {updated} into the tracker.")
        if engine == "heuristic":
            print("Note: offline kits use your master resume as-is + a keyword-gap report;"
                  " edit the [FILL: …] spots in each cover-letter.md before sending.")


if __name__ == "__main__":
    main()
