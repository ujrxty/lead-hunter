import asyncio
import os
import random
import re
from typing import List, Optional
from datetime import datetime
from urllib.parse import quote_plus
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page
from playwright_stealth import Stealth

from app.core.config import settings
from app.schemas.job import JobCreate, SearchRequest

SESSION_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "upwork_session.json")


class UpworkScraper:
    """Scraper for Upwork job listings using Playwright with stealth."""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.stealth = Stealth()

    async def init(self):
        """Initialize the browser."""
        if self.browser is None:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=False,  # Must be non-headless to bypass Cloudflare
                channel="chrome",  # Use installed Chrome
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-automation',
                    '--no-sandbox',
                    '--window-position=-2000,-2000',  # Off-screen
                ]
            )
            logger.info("Browser initialized (non-headless, off-screen)")

    async def close(self):
        """Close the browser."""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        logger.info("Browser closed")

    async def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Add random delay between actions."""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    def _build_search_url(self, request: SearchRequest) -> str:
        """Build Upwork search URL with filters."""
        if request.search_type == "AND":
            query = " ".join(request.keywords)
        else:
            query = " OR ".join(request.keywords)

        encoded_query = quote_plus(query)
        return f"https://www.upwork.com/nx/search/jobs/?q={encoded_query}&sort=recency"

    async def _create_stealth_page(self) -> Page:
        """Create a new page with stealth applied."""
        session_path = os.path.abspath(SESSION_FILE)
        context_kwargs = {
            'viewport': {'width': 1920, 'height': 1080},
        }
        if os.path.exists(session_path):
            context_kwargs['storage_state'] = session_path
            logger.info("Using saved session")
        else:
            logger.warning(f"No session file found at {session_path}. Run save_session.py first.")

        context = await self.browser.new_context(**context_kwargs)
        await self.stealth.apply_stealth_async(context)
        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        return page

    async def search_jobs(self, request: SearchRequest, max_pages: int = 2) -> List[JobCreate]:
        """Search for jobs on Upwork using browser automation."""
        await self.init()
        all_jobs: List[JobCreate] = []
        page = None

        try:
            page = await self._create_stealth_page()
            url = self._build_search_url(request)
            logger.info(f"Navigating to: {url}")

            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await self._random_delay(3, 5)

            # Wait for Cloudflare to clear (up to 30 seconds with retries)
            for attempt in range(6):
                title = await page.title()
                if 'just a moment' not in title.lower():
                    break
                logger.info(f"Cloudflare challenge detected, waiting... (attempt {attempt + 1}/6)")
                await asyncio.sleep(5)

            # Final check for blocks
            if await self._check_for_blocks(page):
                logger.warning("Still blocked after waiting. Session may need refresh.")
                return all_jobs

            for page_num in range(max_pages):
                logger.info(f"Scraping page {page_num + 1}")

                # Wait for job cards to load
                try:
                    await page.wait_for_selector('[data-test="job-tile-list"]', timeout=15000)
                except Exception:
                    logger.warning("Job list not found, trying alternative selector")
                    try:
                        await page.wait_for_selector('article[data-ev-label="search_results_impression"]', timeout=10000)
                    except Exception:
                        logger.error("No job listings found on page")
                        break

                # Extract jobs from current page
                jobs = await self._extract_jobs_from_page(page, request.keywords)
                all_jobs.extend(jobs)
                logger.info(f"Extracted {len(jobs)} jobs from page {page_num + 1}")

                if page_num < max_pages - 1:
                    # Try to go to next page
                    has_next = await self._go_to_next_page(page)
                    if not has_next:
                        logger.info("No more pages available")
                        break
                    await self._random_delay(2, 4)

        except Exception as e:
            logger.error(f"Error during scraping: {e}")
        finally:
            if page:
                await page.context.close()

        logger.info(f"Total jobs scraped: {len(all_jobs)}")
        return all_jobs

    async def _check_for_blocks(self, page: Page) -> bool:
        """Check if we hit a captcha or login requirement."""
        title = await page.title()
        if 'just a moment' in title.lower():
            return True

        content = await page.content()
        blocking_indicators = [
            'access denied',
            'please log in',
            'sign in to continue',
        ]
        content_lower = content.lower()
        for indicator in blocking_indicators:
            if indicator in content_lower:
                return True
        return False

    async def _extract_jobs_from_page(self, page: Page, keywords: List[str]) -> List[JobCreate]:
        """Extract job listings from the current page."""
        jobs: List[JobCreate] = []

        # Try multiple selectors for job cards
        job_cards = await page.query_selector_all('article[data-ev-label="search_results_impression"]')

        if not job_cards:
            job_cards = await page.query_selector_all('[data-test="job-tile"]')

        if not job_cards:
            job_cards = await page.query_selector_all('section.job-tile')

        logger.info(f"Found {len(job_cards)} job cards")

        for card in job_cards:
            try:
                job = await self._parse_job_card(card, keywords)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.error(f"Error parsing job card: {e}")
                continue

        return jobs

    async def _parse_job_card(self, card, keywords: List[str]) -> Optional[JobCreate]:
        """Parse a single job card element."""
        try:
            # Extract title
            title_elem = await card.query_selector('h2 a, [data-test="job-tile-title-link"], .job-tile-title a')
            if not title_elem:
                return None

            title = await title_elem.inner_text()
            title = title.strip()

            # Extract URL
            url = await title_elem.get_attribute('href')
            if url and not url.startswith('http'):
                url = f"https://www.upwork.com{url}"

            # Extract Upwork ID from URL
            upwork_id = self._extract_job_id(url) if url else f"unknown_{random.randint(10000, 99999)}"

            # Extract description
            desc_elem = await card.query_selector('[data-test="job-description-text"], .job-description, p[class*="description"]')
            description = ""
            if desc_elem:
                description = await desc_elem.inner_text()
                description = description.strip()

            # Extract budget info
            budget_type, budget_min, budget_max = await self._extract_budget_from_card(card)

            # Extract client country
            client_country = await self._extract_client_info(card)

            # Extract posted time
            posted_at = await self._extract_posted_time(card)

            return JobCreate(
                upwork_id=upwork_id,
                title=title,
                description=description,
                url=url or "",
                client_country=client_country,
                budget_type=budget_type,
                budget_min=budget_min,
                budget_max=budget_max,
                search_keywords=keywords,
                posted_at=posted_at
            )

        except Exception as e:
            logger.error(f"Error parsing job card: {e}")
            return None

    def _extract_job_id(self, url: str) -> str:
        """Extract job ID from Upwork URL."""
        if not url:
            return f"unknown_{random.randint(10000, 99999)}"

        # URL pattern: /jobs/~01abc123...
        match = re.search(r'/jobs/~(\w+)', url)
        if match:
            return match.group(1)

        # Alternative: /job/title_~01abc123
        match = re.search(r'_~(\w+)', url)
        if match:
            return match.group(1)

        return url.split('/')[-1].split('?')[0].replace('~', '')

    async def _extract_budget_from_card(self, card) -> tuple:
        """Extract budget information from job card."""
        try:
            # Look for budget/rate elements
            budget_elem = await card.query_selector('[data-test="job-type-label"], [data-test="budget"], .job-type-label')
            if budget_elem:
                budget_text = await budget_elem.inner_text()
                budget_text = budget_text.strip()

                # Hourly rate pattern
                hourly_match = re.search(r'\$?([\d,.]+)\s*-\s*\$?([\d,.]+)\s*/\s*hr', budget_text, re.IGNORECASE)
                if hourly_match:
                    return 'hourly', float(hourly_match.group(1).replace(',', '')), float(hourly_match.group(2).replace(',', ''))

                # Fixed price pattern
                fixed_match = re.search(r'\$?([\d,.]+)', budget_text)
                if fixed_match and 'fixed' in budget_text.lower():
                    return 'fixed', float(fixed_match.group(1).replace(',', '')), None

        except Exception as e:
            logger.debug(f"Could not extract budget: {e}")

        return None, None, None

    async def _extract_client_info(self, card) -> Optional[str]:
        """Extract client country from job card."""
        try:
            location_elem = await card.query_selector('[data-test="client-country"], .client-location, [class*="location"]')
            if location_elem:
                return (await location_elem.inner_text()).strip()
        except Exception:
            pass
        return None

    async def _extract_posted_time(self, card) -> Optional[datetime]:
        """Extract posted time from job card."""
        try:
            time_elem = await card.query_selector('[data-test="posted-on"], .job-posted-on, time, [class*="posted"]')
            if time_elem:
                time_text = await time_elem.inner_text()
                return self._parse_relative_time(time_text.strip())
        except Exception:
            pass
        return None

    def _parse_relative_time(self, time_str: str) -> Optional[datetime]:
        """Parse relative time string like '2 hours ago' to datetime."""
        now = datetime.now()
        time_str = time_str.lower()

        patterns = [
            (r'(\d+)\s*minute', 'minutes'),
            (r'(\d+)\s*hour', 'hours'),
            (r'(\d+)\s*day', 'days'),
            (r'(\d+)\s*week', 'weeks'),
            (r'(\d+)\s*month', 'months'),
        ]

        for pattern, unit in patterns:
            match = re.search(pattern, time_str)
            if match:
                value = int(match.group(1))
                if unit == 'minutes':
                    return now.replace(second=0, microsecond=0)
                elif unit == 'hours':
                    from datetime import timedelta
                    return now - timedelta(hours=value)
                elif unit == 'days':
                    from datetime import timedelta
                    return now - timedelta(days=value)
                elif unit == 'weeks':
                    from datetime import timedelta
                    return now - timedelta(weeks=value)
                elif unit == 'months':
                    from datetime import timedelta
                    return now - timedelta(days=value * 30)

        return now

    async def _go_to_next_page(self, page: Page) -> bool:
        """Navigate to the next page of results."""
        try:
            next_btn = await page.query_selector('[data-test="pagination-next"], button[aria-label="Next"], a[aria-label="Next"]')
            if next_btn:
                is_disabled = await next_btn.get_attribute('disabled')
                if is_disabled:
                    return False
                await next_btn.click()
                await page.wait_for_load_state('networkidle', timeout=15000)
                return True
        except Exception as e:
            logger.debug(f"Could not navigate to next page: {e}")
        return False


upwork_scraper = UpworkScraper()
