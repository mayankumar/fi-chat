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
    twilio_voice_number: str = ""  # dedicated voice number for outbound calls (e.g. +91XXXXXXXXXX)

    # Models.
    # NOTE: `haiku_model` is temporarily pointed at Sonnet per user request
    # while we iterate on conversational quality (number parsing, extraction,
    # intent classification). Every call-site that reads `haiku_model`
    # (intent_classifier, language, goal_discovery extraction, agitation,
    # session_memory, dashboard brief) will run on Sonnet until we flip this
    # back to "claude-haiku-4-5-20251001". Override via HAIKU_MODEL env var.
    haiku_model: str = "claude-sonnet-4-6"
    sonnet_model: str = "claude-sonnet-4-6"
    max_tokens: int = 600
    max_history_messages: int = 20

    # Message mode: "split" = separate messages (demo), "compact" = one long message (testing)
    message_mode: str = "compact"

    # Public base URL (for media/PDF URLs — backend ngrok)
    media_base_url: str = ""

    # Dashboard base URL (Next.js app — where /action/{token} landing pages live)
    dashboard_base_url: str = "http://localhost:3000"

    # OpenAI (Whisper STT + TTS for voice messages)
    openai_api_key: str = ""
    voice_replies_enabled: bool = True
    tts_model: str = "tts-1"
    tts_voice: str = "nova"

    # Security
    validate_twilio_signature: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


def config_status() -> dict:
    """Return a startup readiness report.

    Keys: 'ok' — feature is configured; 'missing' — optional feature disabled
    with a one-line reason. Intended to be logged at FastAPI startup so
    operators see what's wired up without digging through a stack trace on
    first use.
    """
    s = get_settings()
    report = {"ok": [], "missing": []}

    # Required — if it were missing, Settings() would have raised earlier.
    report["ok"].append("Anthropic (required)")

    if s.twilio_account_sid and s.twilio_auth_token:
        report["ok"].append(f"Twilio WhatsApp (from={s.twilio_whatsapp_from})")
    else:
        report["missing"].append(
            "Twilio WhatsApp — outbound messages will fail "
            "(set TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN)"
        )

    if s.twilio_api_key_sid and s.twilio_api_key_secret and s.twilio_twiml_app_sid:
        report["ok"].append("Twilio Voice (browser calling)")
    else:
        report["missing"].append(
            "Twilio Voice — advisor-dashboard calling disabled "
            "(needs TWILIO_API_KEY_SID, TWILIO_API_KEY_SECRET, TWILIO_TWIML_APP_SID)"
        )

    if s.openai_api_key:
        report["ok"].append("OpenAI (voice STT/TTS)")
    else:
        report["missing"].append("OpenAI — voice transcription / TTS disabled")

    if s.media_base_url:
        report["ok"].append(f"media_base_url={s.media_base_url}")
    else:
        report["missing"].append(
            "MEDIA_BASE_URL not set — PDF / audio URLs will be unreachable externally"
        )

    report["ok"].append(f"dashboard_base_url={s.dashboard_base_url}")
    report["ok"].append(f"message_mode={s.message_mode}")

    return report
