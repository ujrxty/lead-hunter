"""Session management service for Upwork authentication via UI."""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
from loguru import logger

try:
    import nodriver as uc
except ImportError:
    uc = None


class SessionService:
    """Manages Upwork browser session for scraping."""

    def __init__(self):
        self.session_file = Path(__file__).parent.parent.parent.parent / "upwork_session.json"
        self.browser = None
        self._connection_in_progress = False

    def get_session_status(self) -> Dict:
        """Check current session status."""
        if not self.session_file.exists():
            return {
                "connected": False,
                "message": "No session found. Click Connect to authenticate.",
                "last_connected": None
            }

        try:
            with open(self.session_file, "r") as f:
                data = json.load(f)

            last_connected = data.get("saved_at")
            cookies = data.get("cookies", [])

            if not cookies:
                return {
                    "connected": False,
                    "message": "Session file exists but no cookies found.",
                    "last_connected": last_connected
                }

            # Check if session is likely expired (older than 24 hours)
            if last_connected:
                saved_time = datetime.fromisoformat(last_connected)
                hours_old = (datetime.now() - saved_time).total_seconds() / 3600

                if hours_old > 24:
                    return {
                        "connected": True,
                        "message": f"Session may be expired ({int(hours_old)} hours old). Consider refreshing.",
                        "last_connected": last_connected,
                        "needs_refresh": True
                    }

            return {
                "connected": True,
                "message": "Session active and ready.",
                "last_connected": last_connected,
                "cookies_count": len(cookies)
            }

        except Exception as e:
            logger.error(f"Error reading session: {e}")
            return {
                "connected": False,
                "message": f"Error reading session: {str(e)}",
                "last_connected": None
            }

    async def start_connection(self) -> Dict:
        """Start browser for user to authenticate with Upwork.

        Opens a visible Chrome window where user can:
        1. Complete Cloudflare challenge
        2. Log into Upwork if needed
        3. Session is saved automatically when done
        """
        if self._connection_in_progress:
            return {
                "success": False,
                "message": "Connection already in progress"
            }

        if not uc:
            return {
                "success": False,
                "message": "nodriver not installed. Run: pip install nodriver"
            }

        self._connection_in_progress = True

        try:
            logger.info("Starting browser for Upwork authentication...")

            # Open visible browser (not off-screen)
            self.browser = await uc.start(
                headless=False,
                browser_args=[
                    '--start-maximized',
                    '--disable-blink-features=AutomationControlled'
                ]
            )

            # Navigate to Upwork
            page = await self.browser.get("https://www.upwork.com/nx/search/jobs/")

            return {
                "success": True,
                "message": "Browser opened. Complete Cloudflare and login, then click 'Save Session'.",
                "browser_id": id(self.browser)
            }

        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            self._connection_in_progress = False
            return {
                "success": False,
                "message": f"Failed to open browser: {str(e)}"
            }

    async def save_and_close(self) -> Dict:
        """Save cookies and close browser."""
        if not self.browser:
            self._connection_in_progress = False
            return {
                "success": False,
                "message": "No browser session to save"
            }

        try:
            # Get all cookies from browser
            # nodriver stores cookies automatically, but we can extract them
            page = self.browser.main_tab

            # Get cookies via JavaScript
            cookies_js = await page.evaluate("""
                document.cookie.split(';').map(c => {
                    const [name, ...value] = c.trim().split('=');
                    return { name: name, value: value.join('=') };
                });
            """)

            # Also get cookies from CDP if available
            try:
                cookies = await page.send(uc.cdp.network.get_cookies())
                if cookies:
                    cookies_data = [
                        {
                            "name": c.name,
                            "value": c.value,
                            "domain": c.domain,
                            "path": c.path,
                            "expires": c.expires,
                            "httpOnly": c.http_only,
                            "secure": c.secure
                        }
                        for c in cookies
                    ]
            except:
                cookies_data = cookies_js if cookies_js else []

            # Save session
            session_data = {
                "cookies": cookies_data,
                "saved_at": datetime.now().isoformat(),
                "url": "https://www.upwork.com"
            }

            with open(self.session_file, "w") as f:
                json.dump(session_data, f, indent=2)

            logger.info(f"Session saved with {len(cookies_data)} cookies")

            # Close browser
            self.browser.stop()
            self.browser = None
            self._connection_in_progress = False

            return {
                "success": True,
                "message": f"Session saved successfully with {len(cookies_data)} cookies!",
                "cookies_count": len(cookies_data)
            }

        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            self._connection_in_progress = False

            # Try to close browser anyway
            if self.browser:
                try:
                    self.browser.stop()
                except:
                    pass
                self.browser = None

            return {
                "success": False,
                "message": f"Failed to save session: {str(e)}"
            }

    async def cancel_connection(self) -> Dict:
        """Cancel ongoing connection and close browser."""
        if self.browser:
            try:
                self.browser.stop()
            except:
                pass
            self.browser = None

        self._connection_in_progress = False

        return {
            "success": True,
            "message": "Connection cancelled"
        }

    def is_connection_in_progress(self) -> bool:
        """Check if a connection is currently in progress."""
        return self._connection_in_progress


session_service = SessionService()
