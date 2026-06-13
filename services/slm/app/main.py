import json
import time
from typing import Any

import pika

from .config import settings
from .model import GenerationRequest, build_generator


def connect_with_retry(max_attempts: int = 30) -> pika.BlockingConnection:
    last_error: Exception | None = None
    for _ in range(max_attempts):
        try:
            return pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Could not connect to RabbitMQ: {last_error}")


def main() -> None:
    generator = build_generator()
    connection = connect_with_retry()
    channel = connection.channel()
    channel.queue_declare(queue=settings.slm_request_queue, durable=True)
    channel.basic_qos(prefetch_count=1)

    def on_request(ch: Any, method: Any, props: pika.BasicProperties, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8"))
            req = GenerationRequest(
                prompt=payload["prompt"],
                max_new_tokens=payload.get("max_new_tokens") or settings.max_new_tokens,
            )
            text = generator.generate(req)
            response = {"text": text}
        except Exception as exc:  # noqa: BLE001
            response = {"error": str(exc)}

        if props.reply_to:
            ch.basic_publish(
                exchange="",
                routing_key=props.reply_to,
                properties=pika.BasicProperties(correlation_id=props.correlation_id, content_type="application/json"),
                body=json.dumps(response, ensure_ascii=False).encode("utf-8"),
            )
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=settings.slm_request_queue, on_message_callback=on_request)
    print(f"SLM service consuming queue: {settings.slm_request_queue}; backend={settings.slm_backend}", flush=True)
    channel.start_consuming()


if __name__ == "__main__":
    main()
