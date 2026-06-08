from app.analyzer import analyze_pr
from app.models import ChangedFile, PRJob
from app.report import build_markdown_report


def test_report_contains_core_sections() -> None:
    result = analyze_pr(
        PRJob(owner="local", repo="demo", pull_number=1),
        [ChangedFile(filename="src/app.py", additions=1, changes=1, patch="@@ -1 +1 @@\n+print('x')")],
    )
    result.slm_summary = "SLM text"
    md = build_markdown_report(result)
    assert "# PR Quality Report" in md
    assert "## Deterministic findings" in md
    assert "## SLM-generated context" in md
    assert "SLM text" in md
