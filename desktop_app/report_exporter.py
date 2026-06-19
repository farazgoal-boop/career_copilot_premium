"""Persistence helpers for exported interview learning reports."""

from __future__ import annotations

import json
from pathlib import Path

from .learning_engine import LearningReport


def export_learning_report(report: LearningReport, destination: str | Path) -> Path:
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return target