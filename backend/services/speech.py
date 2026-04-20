"""Voice message support — Whisper STT + OpenAI TTS."""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path

import httpx
import openai

from backend.config import get_settings

logger = logging.getLogger("fi-chat.speech")

AUDIO_DIR = Path("backend/static/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


async def transcribe(audio_url: str, twilio_auth: tuple[str, str]) -> dict:
    """Download audio from Twilio, save locally, and transcribe via OpenAI Whisper.

    Returns:
        {"transcript": str, "audio_url": str} — transcript text + local file URL.
        On failure: {"transcript": "", "audio_url": ""}.
    """
    settings = get_settings()
    empty = {"transcript": "", "audio_url": ""}

    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY not set — cannot transcribe")
        return empty

    tmp_path = None
    try:
        # 1. Download audio from Twilio (requires auth)
        logger.info("Downloading audio from Twilio: %s", audio_url[:80])
        async with httpx.AsyncClient() as client:
            resp = await client.get(audio_url, auth=twilio_auth, follow_redirects=True)
            resp.raise_for_status()

        # Determine extension from content-type
        ct = resp.headers.get("content-type", "audio/ogg")
        ext = ".ogg" if "ogg" in ct else ".mp3" if "mp3" in ct else ".wav" if "wav" in ct else ".ogg"

        # 2. Write to temp file for Whisper
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tmp.write(resp.content)
        tmp.close()
        tmp_path = tmp.name
        logger.info("Audio saved to temp: %s (%d bytes)", tmp_path, len(resp.content))

        # 3. Save a permanent copy to static/audio/ for dashboard playback
        saved_filename = f"voice_in_{uuid.uuid4().hex}{ext}"
        saved_path = AUDIO_DIR / saved_filename
        shutil.copy2(tmp_path, saved_path)

        if settings.media_base_url:
            saved_url = f"{settings.media_base_url}/static/audio/{saved_filename}"
        else:
            saved_url = f"/static/audio/{saved_filename}"
        logger.info("Voice saved permanently: %s", saved_path)

        # 4. Transcribe with Whisper
        oai_client = openai.OpenAI(api_key=settings.openai_api_key)

        def _transcribe():
            with open(tmp_path, "rb") as f:
                result = oai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                )
            return result.text

        transcript = await asyncio.to_thread(_transcribe)
        logger.info("Whisper transcript: %r", transcript[:100] if transcript else "(empty)")

        return {
            "transcript": transcript.strip() if transcript else "",
            "audio_url": saved_url,
        }

    except httpx.HTTPStatusError as e:
        logger.error("Failed to download audio: HTTP %d", e.response.status_code)
        return empty
    except openai.APIError as e:
        logger.error("Whisper API error: %s", e)
        return empty
    except Exception:
        logger.exception("Transcription failed")
        return empty
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def synthesize(text: str) -> str | None:
    """Convert text to speech via OpenAI TTS.

    Returns:
        Public URL of the generated audio file, or None if disabled/failed.
    """
    settings = get_settings()
    if not settings.voice_replies_enabled:
        return None
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set — skipping TTS")
        return None

    # Truncate to TTS limit (4096 chars)
    text = text[:4096]

    try:
        client = openai.OpenAI(api_key=settings.openai_api_key)

        def _synthesize():
            response = client.audio.speech.create(
                model=settings.tts_model,
                voice=settings.tts_voice,
                input=text,
                response_format="mp3",
            )
            return response.content

        audio_bytes = await asyncio.to_thread(_synthesize)

        # Save to static/audio/
        filename = f"voice_out_{uuid.uuid4().hex}.mp3"
        filepath = AUDIO_DIR / filename
        filepath.write_bytes(audio_bytes)
        logger.info("TTS audio saved: %s (%d bytes)", filepath, len(audio_bytes))

        # Return public URL
        if settings.media_base_url:
            return f"{settings.media_base_url}/static/audio/{filename}"
        return f"/static/audio/{filename}"

    except openai.APIError as e:
        logger.error("TTS API error: %s", e)
        return None
    except Exception:
        logger.exception("TTS synthesis failed")
        return None
