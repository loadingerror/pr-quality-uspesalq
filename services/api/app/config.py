from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    rabbitmq_url: str = Field(default="amqp://guest:guest@rabbitmq:5672/", alias="RABBITMQ_URL")
    pr_analysis_queue: str = Field(default="pr.analysis.requests", alias="PR_ANALYSIS_QUEUE")
    github_webhook_secret: str | None = Field(default=None, alias="GITHUB_WEBHOOK_SECRET")

    class Config:
        populate_by_name = True
        env_file = ".env"


settings = Settings()
