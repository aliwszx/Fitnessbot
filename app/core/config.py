from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: str = Field(..., description="Telegram bot token")
    telegram_webhook_url: str = Field(..., description="Public HTTPS URL for webhook")
    secret_token: str = Field(default="changeme", description="Webhook secret token")

    # Supabase
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_key: str = Field(..., description="Supabase anon/service key")

    # Gemini
    gemini_api_key: str = Field(..., description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-1.5-flash", description="Gemini model name")

    # App
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    debug: bool = Field(default=False)

    @property
    def webhook_path(self) -> str:
        return f"/webhook/{self.secret_token}"

    @property
    def webhook_full_url(self) -> str:
        return f"{self.telegram_webhook_url}{self.webhook_path}"


settings = Settings()
