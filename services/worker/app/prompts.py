from __future__ import annotations

import json

from .config import settings
from .models import AnalysisResult


def build_slm_prompt(result: AnalysisResult) -> str:
    files_payload = []
    budget = settings.max_patch_chars
    used = 0
    for f in result.files:
        patch = f.patch or ""
        remaining = max(budget - used, 0)
        if remaining <= 0:
            patch_excerpt = "[patch omitted: context budget exceeded]"
        else:
            patch_excerpt = patch[:remaining]
            used += len(patch_excerpt)
        files_payload.append(
            {
                "filename": f.filename,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "changes": f.changes,
                "patch_excerpt": patch_excerpt,
            }
        )

    facts = {
        "repository": f"{result.job.owner}/{result.job.repo}",
        "pull_request": result.job.pull_number,
        "title": result.job.title,
        "author": result.job.author,
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
        "summary_facts": result.summary_facts,
        "findings": [f.model_dump() for f in result.findings],
        "file_assessments": [f.model_dump() for f in result.file_assessments[:20]],
        "files": files_payload[:30],
    }

    return f"""
You are a senior code reviewer assisting a human who must approve or reject a GitHub Pull Request.

Rules:
- Use ONLY the facts and diff excerpts provided below.
- Do not invent files, risks, tests, or business context that are not present.
- Do not make the final approve/reject decision.
- Be concise and practical.
- Write in English.

Return Markdown with exactly these sections:

## Reviewer summary
## Main risks
## What to check manually
## Questions for the PR author
## Suggested review attention level

Facts:
```json
{json.dumps(facts, ensure_ascii=False, indent=2)}
```
""".strip()
