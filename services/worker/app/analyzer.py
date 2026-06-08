from __future__ import annotations

import re
from pathlib import PurePosixPath

from .models import AnalysisResult, ChangedFile, FileAssessment, Finding, PRJob

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Generic secret assignment", re.compile(r"(?i)(password|passwd|secret|token|api_key)\s*=\s*['\"][^'\"]{8,}['\"]")),
]

PYTHON_RISK_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("high", "security", re.compile(r"\beval\s*\(")),
    ("high", "security", re.compile(r"\bexec\s*\(")),
    ("high", "security", re.compile(r"pickle\.loads\s*\(")),
    ("high", "security", re.compile(r"subprocess\.[A-Za-z_]+\([^\n]*shell\s*=\s*True")),
    ("medium", "reliability", re.compile(r"^\+\s*except\s*:\s*$")),
    ("low", "observability", re.compile(r"^\+\s*print\s*\(")),
    ("low", "maintainability", re.compile(r"(?i)\b(TODO|FIXME|HACK)\b")),
]

INFRA_NAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Makefile",
    ".gitlab-ci.yml",
}
DEPENDENCY_NAMES = {
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "go.mod",
    "go.sum",
}
RISK_PATH_PARTS = {"auth", "security", "payment", "payments", "infra", "migration", "migrations", "iam", "secrets"}
TEST_PATH_PARTS = {"test", "tests", "spec", "specs"}


def _path_parts(filename: str) -> set[str]:
    p = PurePosixPath(filename)
    return set(part.lower() for part in p.parts)


def _is_test_file(filename: str) -> bool:
    parts = _path_parts(filename)
    base = PurePosixPath(filename).name.lower()
    return bool(parts & TEST_PATH_PARTS) or base.startswith("test_") or base.endswith("_test.py") or base.endswith(".spec.ts")


def _is_dependency_file(filename: str) -> bool:
    return PurePosixPath(filename).name in DEPENDENCY_NAMES


def _is_infra_file(filename: str) -> bool:
    path = PurePosixPath(filename)
    return path.name in INFRA_NAMES or ".github/workflows" in filename or "terraform" in _path_parts(filename)


def _extract_added_lines(patch: str | None) -> list[tuple[int | None, str]]:
    if not patch:
        return []
    added: list[tuple[int | None, str]] = []
    new_line_number: int | None = None
    for raw in patch.splitlines():
        if raw.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", raw)
            new_line_number = int(match.group(1)) if match else None
            continue
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("+"):
            added.append((new_line_number, raw))
            if new_line_number is not None:
                new_line_number += 1
        elif raw.startswith("-"):
            continue
        else:
            if new_line_number is not None:
                new_line_number += 1
    return added


def analyze_pr(job: PRJob, files: list[ChangedFile]) -> AnalysisResult:
    findings: list[Finding] = []
    file_assessments: list[FileAssessment] = []

    total_additions = sum(f.additions for f in files)
    total_deletions = sum(f.deletions for f in files)
    total_changes = sum(f.changes for f in files)
    has_tests_changed = any(_is_test_file(f.filename) for f in files)
    has_dependency_changes = any(_is_dependency_file(f.filename) for f in files)
    has_infra_changes = any(_is_infra_file(f.filename) for f in files)

    base_risk = 0
    summary_facts: list[str] = []

    if total_changes > 1000:
        base_risk += 20
        summary_facts.append("PR is very large: more than 1000 changed lines.")
    elif total_changes > 500:
        base_risk += 12
        summary_facts.append("PR is large: more than 500 changed lines.")
    elif total_changes > 200:
        base_risk += 6
        summary_facts.append("PR has moderate size: more than 200 changed lines.")

    if has_dependency_changes:
        base_risk += 8
        summary_facts.append("Dependency manifest or lock file changed.")
    if has_infra_changes:
        base_risk += 10
        summary_facts.append("Infrastructure, Docker, CI/CD or deployment file changed.")

    source_files_changed = any(not _is_test_file(f.filename) for f in files)
    if source_files_changed and not has_tests_changed:
        base_risk += 12
        findings.append(
            Finding(
                severity="medium",
                category="test_coverage",
                message="Source files changed, but no test files were changed in this PR.",
            )
        )

    for f in files:
        risk_points = 0
        reasons: list[str] = []
        parts = _path_parts(f.filename)

        if _is_dependency_file(f.filename):
            risk_points += 8
            reasons.append("dependency file")
        if _is_infra_file(f.filename):
            risk_points += 10
            reasons.append("infra/deployment file")
        risky_parts = parts & RISK_PATH_PARTS
        if risky_parts:
            risk_points += 10
            reasons.append(f"sensitive path: {', '.join(sorted(risky_parts))}")
        if f.changes > 300:
            risk_points += 8
            reasons.append("large file-level diff")
        if f.status in {"removed", "renamed"}:
            risk_points += 4
            reasons.append(f"status={f.status}")

        for line_no, line in _extract_added_lines(f.patch):
            stripped = line[1:].strip()
            for secret_name, pattern in SECRET_PATTERNS:
                if pattern.search(stripped):
                    risk_points += 20
                    findings.append(
                        Finding(
                            severity="critical",
                            category="secret_leak",
                            file=f.filename,
                            line=line_no,
                            message=f"Possible secret detected: {secret_name}.",
                            evidence=stripped[:180],
                        )
                    )
            if f.filename.endswith(".py"):
                for severity, category, pattern in PYTHON_RISK_PATTERNS:
                    if pattern.search(line):
                        points = {"critical": 20, "high": 14, "medium": 8, "low": 3}[severity]
                        risk_points += points
                        findings.append(
                            Finding(
                                severity=severity,
                                category=category,
                                file=f.filename,
                                line=line_no,
                                message=f"Risky Python pattern matched: `{pattern.pattern}`.",
                                evidence=stripped[:180],
                            )
                        )

        file_assessments.append(
            FileAssessment(
                filename=f.filename,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                changes=f.changes,
                risk_points=risk_points,
                reasons=reasons,
            )
        )
        base_risk += min(risk_points, 30)

    if not files:
        summary_facts.append("No changed files were available for analysis.")

    risk_score = min(base_risk, 100)
    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 35:
        risk_level = "medium"
    else:
        risk_level = "low"

    summary_facts.extend(
        [
            f"Changed files: {len(files)}.",
            f"Total additions/deletions: +{total_additions}/-{total_deletions}.",
            f"Risk score: {risk_score}/100 ({risk_level}).",
        ]
    )

    return AnalysisResult(
        job=job,
        files=files,
        total_additions=total_additions,
        total_deletions=total_deletions,
        total_changes=total_changes,
        risk_score=risk_score,
        risk_level=risk_level,
        summary_facts=summary_facts,
        findings=findings,
        file_assessments=sorted(file_assessments, key=lambda x: x.risk_points, reverse=True),
        has_tests_changed=has_tests_changed,
        has_dependency_changes=has_dependency_changes,
        has_infra_changes=has_infra_changes,
        raw={},
    )
