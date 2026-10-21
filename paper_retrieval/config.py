"""服务配置（环境变量或代码注入，无持久化状态）"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    paper_retrieval_port: int = 8080
    openalex_mailto: str = "research@example.com"
    unpaywall_email: str = "research@example.com"
    api_key: str = ""

    connect_timeout: int = 10
    request_timeout: int = 120
    max_concurrency: int = 10

    user_agent: str = (
        "PaperRetrievalService/1.0 (mailto:research@example.com)"
    )

    scihub_domains: list[str] = [
        "https://sci-hub.ee/",
        "https://www.sci-hub.ren/",
        "https://sci-hub.st/",
        "https://sci-hub.ru/",
        "https://sci-hub.se/",
        "https://sci-hub.wf/",
    ]

    openalex_works_api: str = "https://api.openalex.org/works"
    unpaywall_api: str = "https://api.unpaywall.org/v2"
    max_search_limit: int = 200
