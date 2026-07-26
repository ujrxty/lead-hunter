"""Settings API — let the UI manage API keys and runtime config."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.api.services.settings_service import settings_service, KNOWN_KEYS

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    value: str


@router.get("")
async def get_all_settings() -> Dict[str, Any]:
    """Return all known settings. Secret values are masked."""
    return await settings_service.snapshot()


@router.put("/{key}")
async def update_setting(key: str, update: SettingUpdate):
    """Set or override a setting. Takes effect immediately."""
    if key not in KNOWN_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")
    if update.value == "" or update.value is None:
        raise HTTPException(status_code=400, detail="Value cannot be empty. Use DELETE to clear.")
    await settings_service.set(key, update.value)
    return {"ok": True, "key": key, "source": "db"}


@router.delete("/{key}")
async def clear_setting(key: str):
    """Remove the DB override — falls back to env var / default."""
    if key not in KNOWN_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")
    await settings_service.delete(key)
    return {"ok": True, "key": key}


@router.post("/test/groq")
async def test_groq_connection():
    """Verify the current Groq key works by making a tiny probe call."""
    from groq import Groq
    key = await settings_service.get("groq_api_key")
    model = await settings_service.get("groq_model") or "llama-3.3-70b-versatile"
    if not key:
        return {"ok": False, "error": "No Groq API key configured"}
    try:
        client = Groq(api_key=key)
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        return {"ok": True, "model": model, "sample": r.choices[0].message.content}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
