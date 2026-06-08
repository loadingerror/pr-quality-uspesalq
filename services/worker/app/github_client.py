from __future__ import annotations

from typing import Any

import requests

from .config import settings
from .models import ChangedFile, PRJob


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.github_token
        self.base_url = "https://api.github.com"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": settings.github_api_version,
            "User-Agent": "pr-quality-analyzer/0.1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def list_pull_request_files(self, job: PRJob) -> list[ChangedFile]:
        if job.changed_files:
            return job.changed_files

        files: list[ChangedFile] = []
        page = 1
        while True:
            url = f"{self.base_url}/repos/{job.owner}/{job.repo}/pulls/{job.pull_number}/files"
            response = requests.get(
                url,
                headers=self._headers(),
                params={"per_page": 100, "page": page},
                timeout=30,
            )
            response.raise_for_status()
            batch: list[dict[str, Any]] = response.json()
            if not batch:
                break
            for item in batch:
                files.append(
                    ChangedFile(
                        filename=item["filename"],
                        status=item.get("status", "modified"),
                        additions=item.get("additions", 0),
                        deletions=item.get("deletions", 0),
                        changes=item.get("changes", 0),
                        patch=item.get("patch"),
                    )
                )
            if len(batch) < 100:
                break
            page += 1
        return files

    def post_issue_comment(self, job: PRJob, body: str) -> None:
        if not self.token:
            raise RuntimeError("GITHUB_TOKEN is required to post PR comments")
        url = f"{self.base_url}/repos/{job.owner}/{job.repo}/issues/{job.pull_number}/comments"
        response = requests.post(
            url,
            headers=self._headers(),
            json={"body": body},
            timeout=30,
        )
        response.raise_for_status()
