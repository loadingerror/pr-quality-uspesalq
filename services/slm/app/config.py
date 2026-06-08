from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    rabbitmq_url: str = Field(default="amqp://guest:guest@rabbitmq:5672/", alias="RABBITMQ_URL")
    slm_request_queue: str = Field(default="slm.requests", alias="SLM_REQUEST_QUEUE")
    model_id: str = Field(default="Qwen/Qwen2.5-Coder-0.5B-Instruct", alias="MODEL_ID")
    slm_backend: str = Field(default="transformers", alias="SLM_BACKEND")
    max_new_tokens: int = Field(default=512, alias="MAX_NEW_TOKENS")

    class Config:
        populate_by_name = True
        env_file = ".env"


settings = Settings()
