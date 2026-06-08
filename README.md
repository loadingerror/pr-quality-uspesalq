# PR Quality Analyzer

A service for analyzing Pull Request quality. It collects changes from GitHub, runs deterministic code-quality checks, sends normalized context to a local SLM through RabbitMQ, and generates a review report for the human who approves the PR.

## What is included

- **GitHub webhook/API endpoint**: accepts `pull_request` events or a manual PR analysis request.
- **RabbitMQ**: queue for PR analysis jobs and RPC-style queue for SLM requests.
- **Analysis worker**: receives changed files, analyzes the diff, calculates risk, and builds factual context.
- **SLM inference service**: a separate Docker image with a local small language model for review-summary generation.
- **Reports**: Markdown and JSON reports in the `reports/` directory.
- **Optional GitHub comment**: the final report can be posted back to the GitHub PR.

## Architecture

```mermaid
flowchart LR
    GH[GitHub Pull Request] -->|webhook / manual trigger| API[api-service FastAPI]
    API -->|pr.analysis.requests| MQ[(RabbitMQ)]
    MQ --> Worker[analysis-worker]
    Worker -->|GitHub REST API: PR files/diff| GH
    Worker -->|facts prompt: slm.requests| MQ
    MQ --> SLM[slm-service local model]
    SLM -->|RPC reply| MQ
    MQ --> Worker
    Worker --> Report[reports/*.md + *.json]
    Worker -. optional PR comment .-> GH
```

## Quick local start

1. Create `.env`:

```bash
cp .env.example .env
```

2. Fill the minimum required values:

```bash
GITHUB_TOKEN=ghp_xxx
GITHUB_WEBHOOK_SECRET=change-me
POST_PR_COMMENT=false
```

3. Start the stack:

```bash
docker compose up --build
```

RabbitMQ UI will be available at `http://localhost:15672` (`guest` / `guest`). The API will be available at `http://localhost:8080`.

4. Send a manual PR analysis request:

```bash
curl -X POST http://localhost:8080/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "owner": "octocat",
    "repo": "Hello-World",
    "pull_number": 1
  }'
```

Reports will appear in `./reports`.

## Lightweight smoke test without GitHub

You can pass changed files directly in the payload:

```bash
curl -X POST http://localhost:8080/analyze \
  -H "Content-Type: application/json" \
  --data @examples/local_job.json
```

## SLM inside a Docker image

By default, `services/slm/Dockerfile` downloads the model during image build:

```env
MODEL_ID=Qwen/Qwen2.5-Coder-0.5B-Instruct
SLM_BACKEND=transformers
```

For quick local tests without downloading the model, temporarily enable mock mode:

```env
SLM_BACKEND=mock
```

This keeps the RabbitMQ/RPC architecture intact, but returns a template summary instead of calling the model.

## GitHub webhook

Configure a webhook in your GitHub repository:

- Payload URL: `https://<your-domain>/webhook/github`
- Content type: `application/json`
- Secret: value of `GITHUB_WEBHOOK_SECRET`
- Events: `Pull requests`

The service verifies `X-Hub-Signature-256` when `GITHUB_WEBHOOK_SECRET` is set.

## GitHub Actions option

The file `.github/workflows/pr-quality.yml` shows how to trigger analysis from CI. For real usage, it is usually better to keep the service running continuously and connect it through a GitHub webhook. GitHub Actions can still be useful in self-hosted or restricted environments.

## How the report is built

The report is built in two stages:

1. **Deterministic facts**:
   - PR size;
   - list of changed files;
   - dependency and infrastructure changes;
   - whether tests were changed;
   - risky patterns: `eval`, `exec`, `shell=True`, `pickle.loads`, bare `except`, potential secrets;
   - risk zones: auth, security, migrations, Docker, CI/CD, configuration files.

2. **SLM summary**:
   - the model receives only structured facts and diff excerpts;
   - the model does not make the final approval decision;
   - the final recommendation remains with the human reviewer.

## API

### `GET /health`

API liveness check.

### `POST /analyze`

Manually enqueue a PR for analysis.

```json
{
  "owner": "my-org",
  "repo": "my-repo",
  "pull_number": 42,
  "post_comment": false
}
```

For local mode, you can pass `changed_files` without GitHub:

```json
{
  "owner": "local",
  "repo": "demo",
  "pull_number": 1,
  "changed_files": [
    {
      "filename": "src/app.py",
      "status": "modified",
      "additions": 10,
      "deletions": 2,
      "changes": 12,
      "patch": "@@ -1,2 +1,5 @@\n+print('debug')\n"
    }
  ]
}
```

### `POST /webhook/github`

Endpoint for GitHub `pull_request` webhooks.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `RABBITMQ_URL` | AMQP URL | `amqp://guest:guest@rabbitmq:5672/` |
| `PR_ANALYSIS_QUEUE` | PR analysis job queue | `pr.analysis.requests` |
| `SLM_REQUEST_QUEUE` | model request queue | `slm.requests` |
| `GITHUB_TOKEN` | GitHub token for reading PRs and posting comments | empty |
| `GITHUB_WEBHOOK_SECRET` | secret for webhook signature verification | empty |
| `POST_PR_COMMENT` | post report as a PR comment | `false` |
| `REPORTS_DIR` | reports directory | `/app/reports` |
| `MODEL_ID` | Hugging Face model | `Qwen/Qwen2.5-Coder-0.5B-Instruct` |
| `SLM_BACKEND` | `transformers` or `mock` | `transformers` |

## Development commands

```bash
make up
make down
make logs
make test-worker
```

## MVP limitations

- The analyzer works on PR diff and metadata; it does not build a full AST of the entire project.
- The SLM must not block merges automatically: it assists the reviewer but does not replace code review.
- Large PRs should use diff chunking and persistent result storage, such as PostgreSQL or S3.
- Production deployments should prefer GitHub App installation tokens over long-lived personal access tokens.

## Recommended next improvements

- Add Python/JavaScript AST analysis.
- Add Semgrep, Bandit, and Ruff checks to the worker.
- Add a database for historical PR quality metrics.
- Add quality gates based on risk scoring.
- Add vector memory for previous PRs in the same project.
- Add comparison against team-specific coding standards.

## Sources

- [GitHub Docs — Webhook events and payloads: pull_request](https://docs.github.com/en/webhooks/webhook-events-and-payloads#pull_request)
- [GitHub Docs — REST API: Pull requests](https://docs.github.com/en/rest/pulls/pulls)
- [GitHub Docs — REST API: Review comments](https://docs.github.com/en/rest/pulls/comments)
- [GitHub Docs — REST API: Create an issue comment](https://docs.github.com/en/rest/issues/comments#create-an-issue-comment)
- [GitHub Docs — Securing your webhooks](https://docs.github.com/en/webhooks/using-webhooks/securing-your-webhooks)
- [Docker Hub — RabbitMQ official image](https://hub.docker.com/_/rabbitmq)
- [RabbitMQ Docs — Work Queues](https://www.rabbitmq.com/tutorials/tutorial-two-python)
- [RabbitMQ Docs — RPC pattern](https://www.rabbitmq.com/tutorials/tutorial-six-python)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Pika Docs — Python RabbitMQ client](https://pika.readthedocs.io/)
- [Hugging Face — Qwen/Qwen2.5-Coder-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct)
- [Qwen2.5-Coder Technical Report](https://arxiv.org/abs/2409.12186)
- [Docker Docs — Compose file reference](https://docs.docker.com/reference/compose-file/)
- [GitHub Docs — GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
