"""Core data shapes shared across the pipeline."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Job:
    """A normalized job posting from any source."""
    title: str
    company: str
    url: str
    source: str
    location: str = ""
    description: str = ""
    posted_at: datetime | None = None
    remote: bool | None = None
    salary: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        """Stable dedupe key — same role from two sources collapses to one."""
        basis = f"{self.company.strip().lower()}|{self.title.strip().lower()}"
        return hashlib.sha1(basis.encode()).hexdigest()[:16]

    def age_days(self, now: datetime | None = None) -> float | None:
        if self.posted_at is None:
            return None
        now = now or datetime.now(timezone.utc)
        return (now - self.posted_at).total_seconds() / 86400
