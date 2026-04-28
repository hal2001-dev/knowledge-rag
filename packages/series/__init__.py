"""TASK-020 (ADR-029): Series/묶음 1급 시민 — 색인 시점 자동 묶기 + 사후 검수."""

from packages.series.matcher import (
    SeriesCandidate,
    Confidence,
    find_candidates,
    extract_volume_number,
    common_prefix,
)
from packages.series.match_runner import series_match_for_doc

__all__ = [
    "SeriesCandidate",
    "Confidence",
    "find_candidates",
    "extract_volume_number",
    "common_prefix",
    "series_match_for_doc",
]
