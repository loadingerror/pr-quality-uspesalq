from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    rabbitmq_url: str = Field(default="amqp://guest:guest@rabbitmq:5672/", alias="RABBITMQ_URL")
    pr_analysis_queue: str = Field(default="pr.analysis.requests", alias="PR_ANALYSIS_QUEUE")
    slm_request_queue: str = Field(default="slm.requests", alias="SLM_REQUEST_QUEUE")
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    github_api_version: str = Field(default="2022-11-28", alias="GITHUB_API_VERSION")
    post_pr_comment: bool = Field(default=False, alias="POST_PR_COMMENT")
    reports_dir: str = Field(default="/app/reports", alias="REPORTS_DIR")
    slm_timeout_seconds: int = Field(default=180, alias="SLM_TIMEOUT_SECONDS")
    max_patch_chars: int = Field(default=12000, alias="MAX_PATCH_CHARS")

    class Config:
        populate_by_name = True
        env_file = ".env"


settings = Settings()
