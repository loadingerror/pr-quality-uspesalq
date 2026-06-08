from typing import Any

from pydantic import BaseModel, Field


class ChangedFile(BaseModel):
    filename: str
    status: str = "modified"
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None


class PRJob(BaseModel):
    owner: str
    repo: str
    pull_number: int = Field(gt=0)
    source: str | None = None
    title: str | None = None
    html_url: str | None = None
    author: str | None = None
    base_sha: str | None = None
    head_sha: str | None = None
    post_comment: bool | None = None
    changed_files: list[ChangedFile] | None = None


class Finding(BaseModel):
    severity: str
    category: str
    file: str | None = None
    line: int | None = None
    message: str
    evidence: str | None = None


class FileAssessment(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    risk_points: int
    reasons: list[str]


class AnalysisResult(BaseModel):
    job: PRJob
    files: list[ChangedFile]
    total_additions: int
    total_deletions: int
    total_changes: int
    risk_score: int
    risk_level: str
    summary_facts: list[str]
    findings: list[Finding]
    file_assessments: list[FileAssessment]
    has_tests_changed: bool
    has_dependency_changes: bool
    has_infra_changes: bool
    slm_summary: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
