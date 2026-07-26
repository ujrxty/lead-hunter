"""Session management routes for Upwork authentication."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import asyncio
from loguru import logger

from app.api.services.session_service import session_service

router = APIRouter(prefix="/session", tags=["session"])


class SessionStatusResponse(BaseModel):
    connected: bool
    message: str
    last_connected: Optional[str] = None
    needs_refresh: Optional[bool] = False
    cookies_count: Optional[int] = None


class ConnectionResponse(BaseModel):
    success: bool
    message: str
    browser_id: Optional[int] = None
    cookies_count: Optional[int] = None


@router.get("/status", response_model=SessionStatusResponse)
async def get_session_status():
    """Check current Upwork session status.

    Returns whether a valid session exists and when it was last saved.
    """
    status = session_service.get_session_status()
    return SessionStatusResponse(**status)


@router.post("/connect", response_model=ConnectionResponse)
async def start_connection():
    """Start browser for Upwork authentication.

    Opens a visible Chrome window where the user can:
    1. Complete Cloudflare challenge
    2. Log into Upwork if needed

    After completing authentication, call /session/save to save the session.

    Security note: This runs on localhost only and requires physical user interaction.
    """
    if session_service.is_connection_in_progress():
        raise HTTPException(
            status_code=409,
            detail="A connection is already in progress. Complete or cancel it first."
        )

    result = await session_service.start_connection()

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])

    return ConnectionResponse(**result)


@router.post("/save", response_model=ConnectionResponse)
async def save_session():
    """Save current browser session and close the browser.

    Call this after completing authentication in the browser.
    Saves cookies for future scraping sessions.
    """
    if not session_service.is_connection_in_progress():
        raise HTTPException(
            status_code=400,
            detail="No connection in progress. Start a connection first."
        )

    result = await session_service.save_and_close()

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])

    return ConnectionResponse(**result)


@router.post("/cancel", response_model=ConnectionResponse)
async def cancel_connection():
    """Cancel ongoing connection and close browser without saving."""
    result = await session_service.cancel_connection()
    return ConnectionResponse(**result)


@router.post("/refresh", response_model=ConnectionResponse)
async def refresh_session():
    """Refresh existing session (shortcut for connect -> save flow).

    Opens browser for re-authentication if current session is expired.
    """
    # Check current status
    status = session_service.get_session_status()

    if status.get("connected") and not status.get("needs_refresh"):
        return ConnectionResponse(
            success=True,
            message="Session is still valid, no refresh needed.",
            cookies_count=status.get("cookies_count")
        )

    # Start new connection
    result = await session_service.start_connection()

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])

    return ConnectionResponse(
        success=True,
        message="Browser opened for re-authentication. Complete login and click Save.",
        browser_id=result.get("browser_id")
    )


@router.get("/health")
async def session_health():
    """Quick health check for session endpoints.

    Security: This endpoint is rate-limited and returns minimal info.
    """
    return {
        "status": "ok",
        "connection_in_progress": session_service.is_connection_in_progress()
    }
