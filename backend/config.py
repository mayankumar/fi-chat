from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Anthropic
    anthropic_api_key: str

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    # Twilio Voice (Browser SDK) — create at console.twilio.com/us1/account/keys-credentials/api-keys
    twilio_api_key_sid: str = ""
    twilio_api_key_secret: str = ""
    twilio_twiml_app_sid: str = ""

    # Models
    haiku_model: str = "claude-haiku-4-5-20251001"
    sonnet_model: str = "claude-sonnet-4-6"
    max_tokens: int = 600
    max_history_messages: int = 20

    # Message mode: "split" = separate messages (demo), "compact" = one long message (testing)
    message_mode: str = "compact"

    # Public base URL (for media/PDF URLs)
    media_base_url: str = ""

    # Security
    validate_twilio_signature: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
