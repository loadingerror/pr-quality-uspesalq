from typing import Any

import requests

from .config import settings
from .models import ChangedFile, PRJob

COMMENT_MARKER = "<!-- pr-quality-analyzer-report -->"


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.github_token
        self.base_url = settings.github_api_base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": settings.github_api_version,
            "User-Agent": "pr-quality-analyzer/1.1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path_or_url: str, **kwargs: Any) -> Any:
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}{path_or_url}"
        response = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else None

    def _paged_get(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self._request("GET", path, params={"per_page": 100, "page": page, **(params or {})})
            if not batch:
                return items
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1

    def get_pull_request(self, job: PRJob) -> PRJob:
        pr = self._request("GET", f"/repos/{job.owner}/{job.repo}/pulls/{job.pull_number}")
        return job.model_copy(
            update={
                "title": job.title or pr.get("title"),
                "html_url": job.html_url or pr.get("html_url"),
                "author": job.author or (pr.get("user") or {}).get("login"),
                "base_sha": job.base_sha or (pr.get("base") or {}).get("sha"),
                "head_sha": job.head_sha or (pr.get("head") or {}).get("sha"),
                "pr_body": job.pr_body if job.pr_body is not None else pr.get("body"),
                "draft": job.draft if job.draft is not None else pr.get("draft"),
            }
        )

    def list_pull_request_files(self, job: PRJob) -> list[ChangedFile]:
        files = self._paged_get(f"/repos/{job.owner}/{job.repo}/pulls/{job.pull_number}/files")
        return [
            ChangedFile(
                filename=item["filename"],
                status=item.get("status", "modified"),
                additions=item.get("additions", 0),
                deletions=item.get("deletions", 0),
                changes=item.get("changes", 0),
                patch=item.get("patch"),
                previous_filename=item.get("previous_filename"),
            )
            for item in files
        ]

    def list_pr_comments(self, job: PRJob) -> list[dict[str, Any]]:
        self._require_token("list PR comments")
        return self._paged_get(f"/repos/{job.owner}/{job.repo}/issues/{job.pull_number}/comments")

    def create_pr_comment(self, job: PRJob, body: str) -> None:
        self._require_token("post PR comments")
        self._request("POST", f"/repos/{job.owner}/{job.repo}/issues/{job.pull_number}/comments", json={"body": body})

    def update_pr_comment(self, comment_url: str, body: str) -> None:
        self._require_token("update PR comments")
        self._request("PATCH", comment_url, json={"body": body})

    def upsert_pr_report_comment(self, job: PRJob, body: str, marker: str = COMMENT_MARKER) -> str:
        if marker not in body:
            body = f"{marker}\n\n{body}"

        if settings.update_existing_comment:
            for comment in self.list_pr_comments(job):
                if marker in (comment.get("body") or ""):
                    self.update_pr_comment(comment["url"], body)
                    return "updated"

        self.create_pr_comment(job, body)
        return "created"

    def _require_token(self, action: str) -> None:
        if not self.token:
            raise RuntimeError(f"GITHUB_TOKEN is required to {action}")
