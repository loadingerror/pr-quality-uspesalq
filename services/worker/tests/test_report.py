from app.analyzer import analyze_pr
from app.github_client import COMMENT_MARKER, GitHubClient
from app.models import ChangedFile, PRJob
from app.report import build_markdown_report, build_pr_comment


def _sample_result():
    result = analyze_pr(
        PRJob(owner="local", repo="demo", pull_number=1, pr_body="Test PR"),
        [ChangedFile(filename="src/app.py", additions=1, changes=1, patch="@@ -1 +1 @@\n+print('x')")],
    )
    result.slm_summary = "SLM text"
    return result


def test_report_contains_core_sections() -> None:
    md = build_markdown_report(_sample_result())
    assert "# PR Quality Report" in md
    assert "## Deterministic findings" in md
    assert "## SLM-generated context" in md
    assert "SLM text" in md


def test_pr_comment_contains_reviewer_sections() -> None:
    comment = build_pr_comment(_sample_result())
    assert "## PR Quality Report" in comment
    assert "### Main deterministic findings" in comment
    assert "### SLM reviewer context" in comment
    assert "### Human approval checklist" in comment


def test_github_comment_upsert_updates_existing_comment(monkeypatch) -> None:
    client = GitHubClient(token="token")
    job = PRJob(owner="local", repo="demo", pull_number=1)
    calls = {"created": 0, "updated": 0}

    monkeypatch.setattr(client, "list_pr_comments", lambda _job: [{"url": "https://api.github.test/comment/1", "body": COMMENT_MARKER}])

    def fake_update(_url: str, body: str):
        calls["updated"] += 1
        assert COMMENT_MARKER in body
        return {}

    def fake_create(_job, _body):
        calls["created"] += 1
        return {}

    monkeypatch.setattr(client, "update_pr_comment", fake_update)
    monkeypatch.setattr(client, "create_pr_comment", fake_create)

    action = client.upsert_pr_report_comment(job, "body")
    assert action == "updated"
    assert calls == {"created": 0, "updated": 1}


def test_github_comment_upsert_creates_when_no_marker(monkeypatch) -> None:
    client = GitHubClient(token="token")
    job = PRJob(owner="local", repo="demo", pull_number=1)
    calls = {"created": 0, "updated": 0}

    monkeypatch.setattr(client, "list_pr_comments", lambda _job: [])

    def fake_update(_url: str, _body: str):
        calls["updated"] += 1
        return {}

    def fake_create(_job, body: str):
        calls["created"] += 1
        assert COMMENT_MARKER in body
        return {}

    monkeypatch.setattr(client, "update_pr_comment", fake_update)
    monkeypatch.setattr(client, "create_pr_comment", fake_create)

    action = client.upsert_pr_report_comment(job, "body")
    assert action == "created"
    assert calls == {"created": 1, "updated": 0}
