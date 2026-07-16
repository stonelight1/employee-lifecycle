from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8013
    # 前端
    frontend_url: str = "http://localhost:5178"

    # 单用户操作者
    local_operator_id: str = "1"
    local_operator_name: str = "LOCAL_HR"

    # SQLite
    database_url: str = "sqlite:///./data/employee_lifecycle.db"

    # 日志
    log_level: str = "INFO"
    log_dir: str = "./logs"

    # 沟通文本
    communication_text_max_length: int = 50000

    # AI
    ai_enabled: bool = False
    ai_provider: Optional[str] = None
    ai_api_url: Optional[str] = None
    ai_model: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_timeout: int = 30
    ai_max_retries: int = 2
    ai_daily_limit: int = 100
    ai_monthly_limit: int = 2000

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
