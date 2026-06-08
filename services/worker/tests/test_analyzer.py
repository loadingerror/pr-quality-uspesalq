from app.analyzer import analyze_pr
from app.models import ChangedFile, PRJob


def test_analyzer_detects_risky_patterns() -> None:
    job = PRJob(owner="local", repo="demo", pull_number=1)
    files = [
        ChangedFile(
            filename="src/payment/callback.py",
            additions=5,
            deletions=0,
            changes=5,
            patch="@@ -1,0 +1,5 @@\n+import pickle\n+def x(payload):\n+    pickle.loads(payload)\n+    subprocess.run('x', shell=True)\n+    print('debug')\n",
        )
    ]
    result = analyze_pr(job, files)
    assert result.risk_score > 0
    assert result.risk_level in {"medium", "high"}
    assert any(f.category == "security" for f in result.findings)
    assert any(f.category == "test_coverage" for f in result.findings)


def test_analyzer_detects_test_change() -> None:
    job = PRJob(owner="local", repo="demo", pull_number=1)
    files = [ChangedFile(filename="tests/test_app.py", additions=10, changes=10)]
    result = analyze_pr(job, files)
    assert result.has_tests_changed is True
