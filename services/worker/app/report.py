from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import AnalysisResult


def _severity_icon(severity: str) -> str:
    return {
        "critical": "🚨",
        "high": "🔴",
        "medium": "🟠",
        "low": "🟡",
    }.get(severity, "ℹ️")


def build_markdown_report(result: AnalysisResult) -> str:
    job = result.job
    title = job.title or f"PR #{job.pull_number}"
    url_part = f"\n\nPR: {job.html_url}" if job.html_url else ""

    lines: list[str] = [
        f"# PR Quality Report — {job.owner}/{job.repo} #{job.pull_number}",
        "",
        f"**Title:** {title}",
        f"**Author:** {job.author or 'unknown'}",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Risk score:** {result.risk_score}/100",
        f"**Risk level:** `{result.risk_level}`",
        url_part.strip(),
        "",
        "## Executive facts",
    ]
    lines.extend([f"- {fact}" for fact in result.summary_facts])

    lines.extend(
        [
            "",
            "## Human review recommendation",
        ]
    )
    if result.risk_level == "high":
        lines.append("Manual review is mandatory. Focus on security, dependency/infra changes and test coverage before approval.")
    elif result.risk_level == "medium":
        lines.append("Manual review is recommended. Confirm changed behavior, edge cases and test adequacy.")
    else:
        lines.append("Low-risk PR by static heuristics, but reviewer should still validate intent and correctness.")

    lines.extend(["", "## Deterministic findings"])
    if not result.findings:
        lines.append("No deterministic findings were detected.")
    else:
        for finding in result.findings:
            location = f" `{finding.file}:{finding.line}`" if finding.file and finding.line else (f" `{finding.file}`" if finding.file else "")
            evidence = f" Evidence: `{finding.evidence}`" if finding.evidence else ""
            lines.append(f"- {_severity_icon(finding.severity)} **{finding.severity}/{finding.category}**{location}: {finding.message}{evidence}")

    lines.extend(["", "## File risk table", "", "| File | Status | + | - | Risk points | Reasons |", "|---|---:|---:|---:|---:|---|"])
    for f in result.file_assessments:
        reasons = ", ".join(f.reasons) if f.reasons else "-"
        lines.append(f"| `{f.filename}` | {f.status} | {f.additions} | {f.deletions} | {f.risk_points} | {reasons} |")

    lines.extend(["", "## SLM-generated context for reviewer"])
    lines.append(result.slm_summary or "SLM summary was not generated.")

    lines.extend(
        [
            "",
            "## Approval checklist",
            "- [ ] The changes match the stated PR goal.",
            "- [ ] Security risks were manually reviewed.",
            "- [ ] Dependency and infrastructure changes are understood and justified.",
            "- [ ] Test coverage is sufficient, or the lack of tests is explicitly justified.",
            "- [ ] No secrets, debug code, or temporary workarounds remain.",
        ]
    )
    return "\n".join(line for line in lines if line is not None)


def save_reports(result: AnalysisResult, reports_dir: str) -> tuple[Path, Path]:
    path = Path(reports_dir)
    path.mkdir(parents=True, exist_ok=True)
    slug = f"{result.job.owner}_{result.job.repo}_pr_{result.job.pull_number}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    md_path = path / f"{slug}.md"
    json_path = path / f"{slug}.json"
    md_path.write_text(build_markdown_report(result), encoding="utf-8")
    json_path.write_text(json.dumps(result.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path
