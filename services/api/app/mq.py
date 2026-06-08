import json
import time
from typing import Any

import pika

from .config import settings


def _connect_with_retry(max_attempts: int = 20) -> pika.BlockingConnection:
    last_error: Exception | None = None
    for _ in range(max_attempts):
        try:
            return pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Could not connect to RabbitMQ: {last_error}")


def publish_pr_analysis_job(payload: dict[str, Any]) -> None:
    connection = _connect_with_retry()
    try:
        channel = connection.channel()
        channel.queue_declare(queue=settings.pr_analysis_queue, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=settings.pr_analysis_queue,
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )
    finally:
        connection.close()
