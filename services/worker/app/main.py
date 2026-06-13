import json
import time
from typing import Any

import pika
from pydantic import ValidationError

from .analyzer import analyze_pr
from .config import settings
from .github_client import GitHubClient
from .models import PRJob
from .prompts import build_slm_prompt
from .report import build_pr_comment, save_reports
from .slm_rpc import SLMRpcClient


def connect_with_retry(max_attempts: int = 30) -> pika.BlockingConnection:
    last_error: Exception | None = None
    for _ in range(max_attempts):
        try:
            return pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Could not connect to RabbitMQ: {last_error}")


def generate_slm_summary(prompt: str) -> str:
    try:
        slm = SLMRpcClient()
        try:
            return slm.generate(prompt=prompt)
        finally:
            slm.close()
    except Exception as exc:  # noqa: BLE001
        return f"SLM summary unavailable: {exc}"


def process_job(payload: dict[str, Any]) -> None:
    job = PRJob.model_validate(payload)
    github = GitHubClient()

    if job.changed_files:
        files = job.changed_files
    else:
        job = github.get_pull_request(job)
        files = github.list_pull_request_files(job)

    result = analyze_pr(job, files)
    result.slm_summary = generate_slm_summary(build_slm_prompt(result))

    md_path, json_path = save_reports(result, settings.reports_dir)
    print(f"Saved reports: {md_path} and {json_path}", flush=True)

    should_comment = job.post_comment if job.post_comment is not None else settings.post_pr_comment
    if should_comment:
        comment = build_pr_comment(result)
        action = github.upsert_pr_report_comment(job, _truncate_comment(comment))
        print(f"GitHub PR comment {action}: {job.owner}/{job.repo}#{job.pull_number}", flush=True)


def _truncate_comment(comment: str, limit: int = 60000) -> str:
    if len(comment) <= limit:
        return comment
    return comment[: limit - 1000] + "\n\n_Report truncated because GitHub comments have size limits._"


def on_message(channel: Any, method: Any, _properties: pika.BasicProperties, body: bytes) -> None:
    try:
        process_job(json.loads(body.decode("utf-8")))
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except ValidationError as exc:
        print(f"Invalid job payload, discarding: {exc}", flush=True)
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:  # noqa: BLE001
        print(f"Job failed, requeue=false: {exc}", flush=True)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main() -> None:
    connection = connect_with_retry()
    channel = connection.channel()
    channel.queue_declare(queue=settings.pr_analysis_queue, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=settings.pr_analysis_queue, on_message_callback=on_message)
    print(f"Worker consuming queue: {settings.pr_analysis_queue}", flush=True)
    channel.start_consuming()


if __name__ == "__main__":
    main()
