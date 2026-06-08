from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .config import settings
from .mq import publish_pr_analysis_job
from .security import verify_github_signature

app = FastAPI(title="PR Quality Analyzer API", version="0.1.0")


class ChangedFile(BaseModel):
    filename: str
    status: str = "modified"
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None


class ManualAnalyzeRequest(BaseModel):
    owner: str
    repo: str
    pull_number: int = Field(gt=0)
    title: str | None = None
    html_url: str | None = None
    author: str | None = None
    base_sha: str | None = None
    head_sha: str | None = None
    post_comment: bool | None = None
    changed_files: list[ChangedFile] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
def analyze_pr(req: ManualAnalyzeRequest) -> dict[str, Any]:
    payload = req.model_dump(exclude_none=True)
    payload["source"] = "manual"
    publish_pr_analysis_job(payload)
    return {
        "status": "queued",
        "owner": req.owner,
        "repo": req.repo,
        "pull_number": req.pull_number,
    }


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict[str, Any]:
    body = await request.body()
    if not verify_github_signature(body, x_hub_signature_256, settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid GitHub webhook signature")

    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"unsupported event: {x_github_event}"}

    payload = await request.json()
    action = payload.get("action")
    if action not in {"opened", "synchronize", "reopened", "ready_for_review"}:
        return {"status": "ignored", "reason": f"unsupported pull_request action: {action}"}

    pr = payload.get("pull_request") or {}
    repo = payload.get("repository") or {}
    owner = ((repo.get("owner") or {}).get("login"))
    repo_name = repo.get("name")
    pr_number = pr.get("number")

    if not owner or not repo_name or not pr_number:
        raise HTTPException(status_code=400, detail="Webhook payload does not contain owner/repo/pull_request.number")

    job = {
        "source": "github_webhook",
        "owner": owner,
        "repo": repo_name,
        "pull_number": pr_number,
        "title": pr.get("title"),
        "html_url": pr.get("html_url"),
        "author": ((pr.get("user") or {}).get("login")),
        "base_sha": ((pr.get("base") or {}).get("sha")),
        "head_sha": ((pr.get("head") or {}).get("sha")),
    }
    publish_pr_analysis_job(job)
    return {"status": "queued", "owner": owner, "repo": repo_name, "pull_number": pr_number}
