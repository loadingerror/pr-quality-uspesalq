from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True, extra="ignore")

    rabbitmq_url: str = Field(default="amqp://guest:guest@rabbitmq:5672/", alias="RABBITMQ_URL")
    pr_analysis_queue: str = Field(default="pr.analysis.requests", alias="PR_ANALYSIS_QUEUE")
    slm_request_queue: str = Field(default="slm.requests", alias="SLM_REQUEST_QUEUE")
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    github_api_base_url: str = Field(default="https://api.github.com", alias="GITHUB_API_BASE_URL")
    github_api_version: str = Field(default="2022-11-28", alias="GITHUB_API_VERSION")
    post_pr_comment: bool = Field(default=True, alias="POST_PR_COMMENT")
    update_existing_comment: bool = Field(default=True, alias="UPDATE_EXISTING_PR_COMMENT")
    reports_dir: str = Field(default="/app/reports", alias="REPORTS_DIR")
    slm_timeout_seconds: int = Field(default=180, alias="SLM_TIMEOUT_SECONDS")
    max_patch_chars: int = Field(default=12000, alias="MAX_PATCH_CHARS")


settings = Settings()
