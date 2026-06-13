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


def _short_sha(value: str | None) -> str:
    return value[:7] if value else "unknown"


def _risk_badge(risk_level: str) -> str:
    return {
        "high": "🔴 high",
        "medium": "🟠 medium",
        "low": "🟢 low",
    }.get(risk_level, risk_level)


def build_markdown_report(result: AnalysisResult) -> str:
    """Build the full Markdown report saved as a local artifact."""
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
        f"**Base SHA:** `{job.base_sha or 'unknown'}`",
        f"**Head SHA:** `{job.head_sha or 'unknown'}`",
        f"**Draft PR:** `{job.draft}`",
        url_part.strip(),
        "",
        "## Executive facts",
    ]
    lines.extend([f"- {fact}" for fact in result.summary_facts])

    lines.extend(["", "## Human review recommendation"])
    if result.risk_level == "high":
        lines.append("Manual review is mandatory. Focus on security, dependency/infra changes, behavioral impact, and test coverage before approval.")
    elif result.risk_level == "medium":
        lines.append("Manual review is recommended. Confirm changed behavior, edge cases, rollback safety, and test adequacy.")
    else:
        lines.append("Low-risk PR by static heuristics, but reviewer should still validate intent, correctness, and maintainability.")

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
            "- [ ] The changes match the stated PR goal and description.",
            "- [ ] Security-sensitive code paths were manually reviewed.",
            "- [ ] Dependency, Docker, CI/CD, and configuration changes are understood and justified.",
            "- [ ] Test coverage is sufficient, or the lack of tests is explicitly justified.",
            "- [ ] No secrets, debug code, temporary workarounds, or risky patterns remain.",
        ]
    )
    return "\n".join(line for line in lines if line is not None)


def build_pr_comment(result: AnalysisResult) -> str:
    """Build the GitHub PR timeline comment.

    This is intentionally concise but complete enough for human approval. The
    worker creates or updates one PR comment with this body.
    """
    job = result.job
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    top_files = result.file_assessments[:10]
    critical_or_high = [f for f in result.findings if f.severity in {"critical", "high"}]

    lines: list[str] = [
        "## PR Quality Report",
        "",
        f"**Repository:** `{job.owner}/{job.repo}`  ",
        f"**PR:** #{job.pull_number} — {job.title or 'untitled'}  ",
        f"**Generated:** {generated}  ",
        f"**Risk:** {_risk_badge(result.risk_level)} (`{result.risk_score}/100`)  ",
        f"**Range:** `{_short_sha(job.base_sha)}` → `{_short_sha(job.head_sha)}`  ",
        "",
        "### Summary",
    ]
    lines.extend([f"- {fact}" for fact in result.summary_facts])

    lines.extend(["", "### Main deterministic findings"])
    if not result.findings:
        lines.append("No deterministic findings were detected.")
    else:
        for finding in result.findings[:15]:
            location = f" `{finding.file}:{finding.line}`" if finding.file and finding.line else (f" `{finding.file}`" if finding.file else "")
            lines.append(f"- {_severity_icon(finding.severity)} **{finding.severity}/{finding.category}**{location}: {finding.message}")
        if len(result.findings) > 15:
            lines.append(f"- ...and {len(result.findings) - 15} more finding(s) in the saved artifact.")

    if critical_or_high:
        lines.extend(["", "### Approval blocker candidates"])
        for finding in critical_or_high[:8]:
            location = f" `{finding.file}:{finding.line}`" if finding.file and finding.line else (f" `{finding.file}`" if finding.file else "")
            lines.append(f"- {location}: {finding.message}")

    lines.extend(["", "### Highest-risk files", "", "| File | Status | + | - | Risk | Reasons |", "|---|---:|---:|---:|---:|---|"])
    for f in top_files:
        reasons = ", ".join(f.reasons) if f.reasons else "-"
        lines.append(f"| `{f.filename}` | {f.status} | {f.additions} | {f.deletions} | {f.risk_points} | {reasons} |")

    lines.extend(["", "### SLM reviewer context", ""])
    lines.append(result.slm_summary or "SLM summary was not generated.")

    lines.extend(
        [
            "",
            "### Human approval checklist",
            "- [ ] I checked the highest-risk files above.",
            "- [ ] I verified that tests are adequate for the changed behavior.",
            "- [ ] I reviewed dependency, infrastructure, and configuration changes if present.",
            "- [ ] I found no exposed secrets, debug leftovers, or unsafe temporary code.",
            "",
            "_This comment is managed by PR Quality Analyzer and will be updated on new PR commits._",
        ]
    )
    return "\n".join(lines)


def save_reports(result: AnalysisResult, reports_dir: str) -> tuple[Path, Path]:
    path = Path(reports_dir)
    path.mkdir(parents=True, exist_ok=True)
    slug = f"{result.job.owner}_{result.job.repo}_pr_{result.job.pull_number}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    md_path = path / f"{slug}.md"
    json_path = path / f"{slug}.json"
    md_path.write_text(build_markdown_report(result), encoding="utf-8")
    json_path.write_text(json.dumps(result.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path
