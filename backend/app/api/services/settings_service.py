"""Runtime settings service — DB-backed overrides for env vars.

Priority order (highest wins):
  1. DB row in app_settings
  2. Environment variable (.env at boot)
  3. Hardcoded default in Settings class

Reads are in-memory cached to avoid a DB hit on every scrape/AI call;
the cache is invalidated whenever set_setting() is called.
"""
from typing import Optional, Dict, Any
from sqlalchemy import select
from app.core.database import async_session_maker
from app.core.config import settings as env_settings
from app.models.job import AppSetting


# Keys the user is allowed to change from the UI.
# key -> (env_attr, is_secret, description)
KNOWN_KEYS = {
    "groq_api_key": ("groq_api_key", True, "Groq API key for AI features"),
    "groq_model": ("groq_model", False, "Groq model name"),
    "scraper_headless": ("scraper_headless", False, "Run scraper in headless mode (true/false)"),
}


class SettingsService:
    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._loaded = False

    async def _load_all(self):
        async with async_session_maker() as db:
            rows = (await db.execute(select(AppSetting))).scalars().all()
            self._cache = {r.key: r.value for r in rows if r.value is not None}
        self._loaded = True

    async def get(self, key: str) -> Optional[str]:
        """Get a setting: DB override → env var → None."""
        if not self._loaded:
            await self._load_all()
        if key in self._cache and self._cache[key] not in (None, ""):
            return self._cache[key]
        # Fall back to env
        env_attr = KNOWN_KEYS.get(key, (key, False, ""))[0]
        val = getattr(env_settings, env_attr, None)
        return str(val) if val not in (None, "") else None

    async def set(self, key: str, value: str) -> None:
        """Persist a setting to DB and invalidate cache."""
        if key not in KNOWN_KEYS:
            raise ValueError(f"Unknown setting: {key}")
        async with async_session_maker() as db:
            existing = (await db.execute(
                select(AppSetting).where(AppSetting.key == key)
            )).scalar_one_or_none()
            if existing:
                existing.value = value
            else:
                db.add(AppSetting(key=key, value=value))
            await db.commit()
        self._cache[key] = value

    async def delete(self, key: str) -> None:
        """Remove override — falls back to env var."""
        async with async_session_maker() as db:
            existing = (await db.execute(
                select(AppSetting).where(AppSetting.key == key)
            )).scalar_one_or_none()
            if existing:
                await db.delete(existing)
                await db.commit()
        self._cache.pop(key, None)

    async def snapshot(self) -> Dict[str, Any]:
        """All known settings with source labels. Secrets returned masked."""
        if not self._loaded:
            await self._load_all()
        out = {}
        for key, (env_attr, is_secret, desc) in KNOWN_KEYS.items():
            db_val = self._cache.get(key)
            env_val = getattr(env_settings, env_attr, None)
            source = "db" if db_val else ("env" if env_val else "unset")
            effective = db_val or (str(env_val) if env_val else None)
            display = None
            if effective is not None:
                display = self._mask(effective) if is_secret else effective
            out[key] = {
                "source": source,
                "is_set": effective is not None,
                "is_secret": is_secret,
                "value": display,
                "description": desc,
            }
        return out

    @staticmethod
    def _mask(value: str) -> str:
        """Return a preview of a secret without leaking it: 'gsk_...B8VC'."""
        if not value:
            return ""
        if len(value) <= 8:
            return "•" * len(value)
        return f"{value[:4]}…{value[-4:]}"


settings_service = SettingsService()
