from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    frontend_url: str = "http://localhost:5180,http://127.0.0.1:5180,http://localhost:5173,http://127.0.0.1:5173"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    session_expire_minutes: int = 60 * 24 * 7
    password_reset_expire_minutes: int = 30
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 900
    register_rate_limit: int = 5
    register_rate_window_seconds: int = 3600
    forgot_password_rate_limit: int = 5
    forgot_password_rate_window_seconds: int = 3600
    reset_password_rate_limit: int = 10
    reset_password_rate_window_seconds: int = 3600
    email_provider_api_key: str = ""
    session_cookie_name: str = "stocksense_session"
    market_data_provider: str = ""
    market_data_api_key: str = ""
    market_data_base_url: str = ""
    market_data_quote_ttl_seconds: int = 15
    market_data_history_ttl_seconds: int = 300
    market_data_max_history_years: int = 10
    fundamental_data_provider: str = ""
    fundamental_api_key: str = ""
    fundamental_api_base_url: str = ""
    fundamental_cache_ttl_seconds: int = 3600
    fundamental_report_stale_hours: int = 168
    fundamental_valuation_stale_hours: int = 24
    watchlist_max_lists: int = 20
    watchlist_max_stocks: int = 50
    watchlist_name_max_length: int = 80
    watchlist_description_max_length: int = 280
    threshold_max_user_overrides: int = 100
    alert_max_per_user: int = 50
    alert_eval_interval_seconds: int = 300
    news_provider: str = ""
    news_rss_feeds: str = ""
    news_ingest_interval_seconds: int = 900
    news_fetch_timeout_seconds: int = 15
    news_max_items_per_feed: int = 30
    news_default_window_days: int = 7
    ai_provider: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_timeout_seconds: int = 30
    ai_max_output_tokens: int = 800
    ai_runs_per_hour: int = 10
    ai_reuse_minutes: int = 30
    backtest_max_calendar_days: int = 1098
    backtest_max_runs: int = 30
    backtest_worker_interval_seconds: int = 30
    backtest_runs_per_hour: int = 20

    @field_validator("market_data_quote_ttl_seconds")
    @classmethod
    def quote_ttl_bounds(cls, value: int) -> int:
        if value < 1 or value > 900:
            raise ValueError("MARKET_DATA_QUOTE_TTL_SECONDS must be between 1 and 900")
        return value

    @field_validator("market_data_history_ttl_seconds")
    @classmethod
    def history_ttl_bounds(cls, value: int) -> int:
        if value < 1 or value > 3600:
            raise ValueError("MARKET_DATA_HISTORY_TTL_SECONDS must be between 1 and 3600")
        return value

    @field_validator("market_data_max_history_years")
    @classmethod
    def max_history_bounds(cls, value: int) -> int:
        if value < 1 or value > 20:
            raise ValueError("MARKET_DATA_MAX_HISTORY_YEARS must be between 1 and 20")
        return value

    @field_validator("fundamental_cache_ttl_seconds")
    @classmethod
    def fundamental_ttl_bounds(cls, value: int) -> int:
        if value < 1 or value > 86400:
            raise ValueError("FUNDAMENTAL_CACHE_TTL_SECONDS must be between 1 and 86400")
        return value

    @field_validator("fundamental_report_stale_hours", "fundamental_valuation_stale_hours")
    @classmethod
    def fundamental_stale_bounds(cls, value: int) -> int:
        if value < 1 or value > 8760:
            raise ValueError("Fundamental freshness hours must be between 1 and 8760")
        return value

    @field_validator("watchlist_max_lists", "watchlist_max_stocks")
    @classmethod
    def watchlist_count_bounds(cls, value: int) -> int:
        if value < 1 or value > 100:
            raise ValueError("Watchlist limits must be between 1 and 100")
        return value

    @field_validator("threshold_max_user_overrides")
    @classmethod
    def threshold_count_bounds(cls, value: int) -> int:
        if value < 1 or value > 500:
            raise ValueError("THRESHOLD_MAX_USER_OVERRIDES must be between 1 and 500")
        return value

    @field_validator("alert_max_per_user")
    @classmethod
    def alert_count_bounds(cls, value: int) -> int:
        if value < 1 or value > 200:
            raise ValueError("ALERT_MAX_PER_USER must be between 1 and 200")
        return value

    @field_validator("alert_eval_interval_seconds")
    @classmethod
    def alert_interval_bounds(cls, value: int) -> int:
        if value < 30 or value > 3600:
            raise ValueError("ALERT_EVAL_INTERVAL_SECONDS must be between 30 and 3600")
        return value

    @field_validator("news_ingest_interval_seconds")
    @classmethod
    def news_interval_bounds(cls, value: int) -> int:
        if value < 60 or value > 86400:
            raise ValueError("NEWS_INGEST_INTERVAL_SECONDS must be between 60 and 86400")
        return value

    @field_validator("news_fetch_timeout_seconds")
    @classmethod
    def news_timeout_bounds(cls, value: int) -> int:
        if value < 3 or value > 60:
            raise ValueError("NEWS_FETCH_TIMEOUT_SECONDS must be between 3 and 60")
        return value

    @field_validator("news_max_items_per_feed")
    @classmethod
    def news_item_bounds(cls, value: int) -> int:
        if value < 1 or value > 100:
            raise ValueError("NEWS_MAX_ITEMS_PER_FEED must be between 1 and 100")
        return value

    @field_validator("news_default_window_days")
    @classmethod
    def news_window_bounds(cls, value: int) -> int:
        if value < 1 or value > 90:
            raise ValueError("NEWS_DEFAULT_WINDOW_DAYS must be between 1 and 90")
        return value

    @field_validator("ai_timeout_seconds")
    @classmethod
    def ai_timeout_bounds(cls, value: int) -> int:
        if value < 5 or value > 120:
            raise ValueError("AI_TIMEOUT_SECONDS must be between 5 and 120")
        return value

    @field_validator("ai_max_output_tokens")
    @classmethod
    def ai_token_bounds(cls, value: int) -> int:
        if value < 100 or value > 4000:
            raise ValueError("AI_MAX_OUTPUT_TOKENS must be between 100 and 4000")
        return value

    @field_validator("ai_runs_per_hour")
    @classmethod
    def ai_quota_bounds(cls, value: int) -> int:
        if value < 1 or value > 60:
            raise ValueError("AI_RUNS_PER_HOUR must be between 1 and 60")
        return value

    @field_validator("backtest_max_calendar_days")
    @classmethod
    def backtest_range_bounds(cls, value: int) -> int:
        if value < 30 or value > 1098:
            raise ValueError("BACKTEST_MAX_CALENDAR_DAYS must be between 30 and 1098")
        return value

    @field_validator("backtest_max_runs")
    @classmethod
    def backtest_run_bounds(cls, value: int) -> int:
        if value < 1 or value > 100:
            raise ValueError("BACKTEST_MAX_RUNS must be between 1 and 100")
        return value

    @field_validator("app_env")
    @classmethod
    def app_env_name(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "production"}:
            raise ValueError("APP_ENV must be development or production")
        return normalized

    @field_validator("backtest_runs_per_hour")
    @classmethod
    def backtest_quota_bounds(cls, value: int) -> int:
        if value < 1 or value > 60:
            raise ValueError("BACKTEST_RUNS_PER_HOUR must be between 1 and 60")
        return value

    @field_validator("backtest_worker_interval_seconds")
    @classmethod
    def backtest_worker_bounds(cls, value: int) -> int:
        if value < 5 or value > 300:
            raise ValueError("BACKTEST_WORKER_INTERVAL_SECONDS must be between 5 and 300")
        return value

    @field_validator("ai_reuse_minutes")
    @classmethod
    def ai_reuse_bounds(cls, value: int) -> int:
        if value < 0 or value > 1440:
            raise ValueError("AI_REUSE_MINUTES must be between 0 and 1440")
        return value

    @field_validator("watchlist_name_max_length", "watchlist_description_max_length")
    @classmethod
    def watchlist_text_bounds(cls, value: int) -> int:
        if value < 1 or value > 500:
            raise ValueError("Watchlist text limits must be between 1 and 500")
        return value

    @field_validator("cookie_samesite")
    @classmethod
    def normalize_samesite(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE must be lax, strict, or none")
        return normalized

    @model_validator(mode="after")
    def cross_site_cookies_require_https(self) -> "Settings":
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true when COOKIE_SAMESITE is none")
        if self.app_env != "production":
            return self
        if not self.database_url.strip():
            raise ValueError("DATABASE_URL is required when APP_ENV is production")
        if not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true when APP_ENV is production")
        if not self.allowed_origins:
            raise ValueError("FRONTEND_URL is required when APP_ENV is production")
        for origin in self.allowed_origins:
            if not origin.startswith("https://"):
                raise ValueError("FRONTEND_URL must use https when APP_ENV is production")
        host = self.redis_url.lower()
        if "localhost" in host or "127.0.0.1" in host:
            raise ValueError("REDIS_URL must not use a local hostname when APP_ENV is production")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip().rstrip("/") for item in self.frontend_url.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
