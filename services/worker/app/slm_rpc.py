import json
import time
import uuid
from typing import Any

import pika

from .config import settings


class SLMRpcClient:
    def __init__(self) -> None:
        self.connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=settings.slm_request_queue, durable=True)
        result = self.channel.queue_declare(queue="", exclusive=True)
        self.callback_queue = result.method.queue
        self.response: dict[str, Any] | None = None
        self.correlation_id: str | None = None
        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self._on_response,
            auto_ack=True,
        )

    def _on_response(self, _channel: Any, method: Any, props: pika.BasicProperties, body: bytes) -> None:
        if self.correlation_id == props.correlation_id:
            self.response = json.loads(body.decode("utf-8"))

    def generate(self, prompt: str, max_new_tokens: int = 512) -> str:
        self.response = None
        self.correlation_id = str(uuid.uuid4())
        payload = {"prompt": prompt, "max_new_tokens": max_new_tokens}
        self.channel.basic_publish(
            exchange="",
            routing_key=settings.slm_request_queue,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.correlation_id,
                content_type="application/json",
                delivery_mode=2,
            ),
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

        deadline = time.time() + settings.slm_timeout_seconds
        while self.response is None and time.time() < deadline:
            self.connection.process_data_events(time_limit=1)

        if self.response is None:
            raise TimeoutError("SLM response timed out")
        if "error" in self.response:
            raise RuntimeError(f"SLM error: {self.response['error']}")
        return str(self.response.get("text", ""))

    def close(self) -> None:
        if self.connection and not self.connection.is_closed:
            self.connection.close()
