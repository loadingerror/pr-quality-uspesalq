from __future__ import annotations

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
from .report import build_markdown_report, save_reports
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


def process_job(payload: dict[str, Any]) -> None:
    job = PRJob.model_validate(payload)
    gh = GitHubClient()
    files = gh.list_pull_request_files(job)
    result = analyze_pr(job, files)

    try:
        slm = SLMRpcClient()
        try:
            prompt = build_slm_prompt(result)
            result.slm_summary = slm.generate(prompt=prompt)
        finally:
            slm.close()
    except Exception as exc:  # noqa: BLE001
        result.slm_summary = f"SLM summary unavailable: {exc}"

    md_path, json_path = save_reports(result, settings.reports_dir)
    print(f"Saved reports: {md_path} and {json_path}", flush=True)

    should_comment = job.post_comment if job.post_comment is not None else settings.post_pr_comment
    if should_comment:
        comment = build_markdown_report(result)
        if len(comment) > 60000:
            comment = comment[:59000] + "\n\n[Report truncated because GitHub comments have size limits.]"
        gh.post_issue_comment(job, comment)
        print(f"Posted PR comment for {job.owner}/{job.repo}#{job.pull_number}", flush=True)


def on_message(channel: Any, method: Any, _properties: pika.BasicProperties, body: bytes) -> None:
    try:
        payload = json.loads(body.decode("utf-8"))
        process_job(payload)
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
