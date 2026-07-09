"""Shared HTTP helpers for source adapters."""
from __future__ import annotations

import re

import requests

# Some boards (RemoteOK) reject the default python-requests UA.
HEADERS = {"User-Agent": "job-copilot/0.1 (+personal job search)"}
TIMEOUT = 20

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def get_json(url: str, params: dict | None = None):
    resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def strip_html(text: str | None, limit: int = 4000) -> str:
    """Crude HTML -> text so descriptions are usable by the LLM without bloat."""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = (text.replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&#39;", "'").replace("&nbsp;", " "))
    text = _WS_RE.sub(" ", text).strip()
    return text[:limit]
