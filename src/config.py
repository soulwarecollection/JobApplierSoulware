"""Load environment + the master profile."""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PROFILE_PATH = ROOT / "profile" / "master-profile.yaml"
COMPANIES_PATH = ROOT / "companies.yaml"

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")


def load_profile() -> dict:
    with open(PROFILE_PATH) as f:
        return yaml.safe_load(f)


def load_companies() -> dict:
    if not COMPANIES_PATH.exists():
        return {}
    with open(COMPANIES_PATH) as f:
        return yaml.safe_load(f) or {}


def all_keywords(profile: dict) -> list[str]:
    """Flatten every ATS keyword cluster into one lowercased list."""
    out: list[str] = []
    for cluster in (profile.get("ats_keywords") or {}).values():
        out.extend(k.lower() for k in cluster)
    return out


def all_target_titles(profile: dict) -> list[str]:
    out: list[str] = []
    for group in (profile.get("target_roles") or {}).values():
        out.extend(t.lower() for t in group)
    return out


_KW_RE: dict[str, re.Pattern] = {}


def _kw_pattern(kw: str) -> re.Pattern:
    """Whole-token match so 'rag' won't hit 'storage' and 'java' won't hit 'javascript'."""
    r = _KW_RE.get(kw)
    if r is None:
        r = re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])")
        _KW_RE[kw] = r
    return r


def matched_keywords(text: str, keywords) -> list[str]:
    t = text.lower()
    return sorted({k for k in keywords if _kw_pattern(k).search(t)})
