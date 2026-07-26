import asyncio
import json
import os
import random
import re
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from urllib.parse import quote_plus
from loguru import logger
import nodriver as uc

from app.schemas.job import JobCreate, SearchRequest
from app.core.config import settings


SESSION_FILE = Path(__file__).parent.parent.parent.parent / "upwork_session.json"


class NodriverScraper:
    """Scraper for Upwork job listings using Nodriver (undetected Chrome)."""

    def __init__(self):
        self.browser = None

    async def init(self):
        """Initialize the browser."""
        if self.browser is None:
            self.browser = await uc.start(
                headless=settings.scraper_headless,
                browser_args=['--window-position=-2000,-2000']  # Off-screen
            )
            logger.info("Nodriver browser initialized")

    async def _load_session_cookies(self, page) -> bool:
        """Load saved Upwork session cookies into the browser.

        Without this, every scrape hits Cloudflare fresh. The saved session
        (from the UI 'Connect' flow) contains the cf_clearance + login cookies
        that let us skip the challenge.
        """
        if not SESSION_FILE.exists():
            logger.warning(f"No session file at {SESSION_FILE}; scraping may hit Cloudflare")
            return False
        try:
            data = json.loads(SESSION_FILE.read_text())
            cookies = data.get("cookies", [])
            if not cookies:
                logger.warning("Session file has no cookies")
                return False

            # Set cookies via CDP. nodriver exposes `cookies.set_all` on the browser.
            try:
                cookie_objs = []
                for c in cookies:
                    if not c.get("name") or c.get("value") is None:
                        continue
                    obj = {
                        "name": c["name"],
                        "value": str(c["value"]),
                        "domain": c.get("domain") or ".upwork.com",
                        "path": c.get("path") or "/",
                    }
                    if c.get("expires") and c["expires"] > 0:
                        obj["expires"] = c["expires"]
                    if c.get("secure"):
                        obj["secure"] = True
                    if c.get("httpOnly"):
                        obj["httpOnly"] = True
                    cookie_objs.append(obj)

                if hasattr(self.browser, "cookies"):
                    await self.browser.cookies.set_all(cookie_objs)
                    logger.info(f"Loaded {len(cookie_objs)} saved cookies")
                    return True
            except Exception as e:
                logger.warning(f"Cookie set via browser.cookies failed: {e}")

            # Fallback: set via document.cookie (works for non-httpOnly cookies)
            for c in cookies:
                if c.get("httpOnly") or not c.get("name"):
                    continue
                js = f"document.cookie = {json.dumps(c['name'] + '=' + str(c['value']) + '; path=/; domain=' + (c.get('domain') or '.upwork.com'))}"
                try:
                    await page.evaluate(js)
                except Exception:
                    pass
            logger.info(f"Loaded cookies via document.cookie fallback")
            return True
        except Exception as e:
            logger.error(f"Failed to load session cookies: {e}")
            return False

    async def close(self):
        """Close the browser."""
        if self.browser:
            self.browser.stop()
            self.browser = None
            logger.info("Browser closed")

    async def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Add random delay between actions."""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    def _build_search_url(self, request: SearchRequest) -> str:
        """Build Upwork search URL with filters.

        Upwork's search parser is strict: multi-word phrases must be
        quoted when combined with OR, otherwise it treats every word as
        a separate token and returns 0. Single-word keywords stay bare.
        """
        def prep(k: str) -> str:
            k = k.strip()
            # Quote if it contains whitespace, so "Python automation" stays
            # a phrase rather than becoming (Python OR automation).
            return f'"{k}"' if ' ' in k else k

        prepped = [prep(k) for k in request.keywords]
        if request.search_type == "AND":
            # AND is implicit — joining with spaces is what Upwork expects.
            query = " ".join(prepped)
        else:
            query = " OR ".join(prepped)
        encoded_query = quote_plus(query)
        return f"https://www.upwork.com/nx/search/jobs/?q={encoded_query}&sort=recency"

    async def search_jobs(self, request: SearchRequest, max_pages: Optional[int] = None) -> List[JobCreate]:
        """Search for jobs on Upwork using Nodriver.

        max_pages behavior:
        - None or 0: unlimited — scrape until Upwork returns no more results
                     (still hard-capped at 100 pages / ~1000 jobs to avoid runaway).
        - N > 0:     scrape at most N pages.
        The request's own max_pages field (if set) takes precedence over the arg.
        """
        await self.init()
        all_jobs: List[JobCreate] = []
        seen_ids: set = set()

        # Resolve effective limit: request field wins, else the arg, else default 10.
        req_max = getattr(request, "max_pages", None)
        if req_max is not None:
            limit = req_max
        elif max_pages is not None:
            limit = max_pages
        else:
            limit = 10

        HARD_CAP = 100  # safety valve regardless of what user requests
        effective_max = HARD_CAP if limit == 0 else min(limit, HARD_CAP)

        try:
            url = self._build_search_url(request)
            logger.info(f"Navigating to: {url}")

            # First visit upwork.com to establish the cookie domain, then inject saved cookies
            page = await self.browser.get("https://www.upwork.com/")
            await asyncio.sleep(2)
            await self._load_session_cookies(page)

            # Now navigate to the actual search page with cookies in place
            page = await self.browser.get(url)
            await self._random_delay(5, 8)  # Wait for Cloudflare

            # Check page title
            title = await page.evaluate("document.title")
            logger.info(f"Page title: {title}")

            # Wait for Cloudflare to clear
            for attempt in range(6):
                try:
                    title = await page.evaluate("document.title")
                    title = str(title) if title else ""
                    if 'just a moment' not in title.lower():
                        logger.info("Cloudflare cleared!")
                        break
                except Exception:
                    pass
                logger.info(f"Waiting for Cloudflare... (attempt {attempt + 1}/6)")
                await asyncio.sleep(5)

            # Small delay to let page fully load
            await asyncio.sleep(3)

            logger.info(f"Scraping up to {effective_max} pages (limit={limit})")
            empty_pages_in_a_row = 0

            for page_num in range(effective_max):
                logger.info(f"Scraping page {page_num + 1}/{effective_max}")
                await self._random_delay(2, 4)

                # Extract jobs and dedupe by upwork_id — Upwork sometimes
                # repeats results across pages, especially near the tail.
                jobs = await self._extract_jobs(page, request.keywords)
                new_jobs = [j for j in jobs if j.upwork_id and j.upwork_id not in seen_ids]
                for j in new_jobs:
                    seen_ids.add(j.upwork_id)
                all_jobs.extend(new_jobs)
                logger.info(f"Page {page_num + 1}: {len(jobs)} extracted, {len(new_jobs)} new (total {len(all_jobs)})")

                # Stop early if the page returned nothing new — we've hit the end.
                if len(new_jobs) == 0:
                    empty_pages_in_a_row += 1
                    if empty_pages_in_a_row >= 2:
                        logger.info("Two consecutive empty pages — stopping.")
                        break
                else:
                    empty_pages_in_a_row = 0

                if page_num < effective_max - 1:
                    if not await self._go_to_next_page(page, page_num):
                        logger.info("Next page unavailable — stopping.")
                        break

        except Exception as e:
            logger.error(f"Error during scraping: {e}")
        finally:
            await self.close()

        logger.info(f"Total jobs scraped: {len(all_jobs)}")
        return all_jobs

    async def _extract_jobs(self, page, keywords: List[str]) -> List[JobCreate]:
        """Extract job listings from the current page."""
        jobs: List[JobCreate] = []

        # Get all job cards via JavaScript - Enhanced extraction with multiple fallbacks
        script = """
            const cards = document.querySelectorAll('article[data-ev-label="search_results_impression"], section.job-tile, [data-test="job-tile"]');
            const result = Array.from(cards).map(card => {
                // Title and URL - multiple selectors
                const titleEl = card.querySelector('h2 a, h3 a, [data-test="job-tile-title-link"], a.job-title-link');

                // Description - try multiple locations
                const descEl = card.querySelector('[data-test="job-description-text"], [data-test="JobDescription"], .job-description, .text-body-sm');

                // Budget/Rate info - look for various patterns
                const budgetEl = card.querySelector('[data-test="job-type-label"], [data-test="budget"], [data-test="is-fixed-price"], .job-type-label');
                const hourlyEl = card.querySelector('[data-test="hourly-rate"], .hourly-rate');
                const fixedEl = card.querySelector('[data-test="fixed-price"], .fixed-price');

                // Location
                const locationEl = card.querySelector('[data-test="client-country"], [data-test="location"], .client-location, [data-test="client-location"]');

                // Posted time - multiple attempts
                const timeEl = card.querySelector('[data-test="posted-on"], [data-test="UpCRelativeTime"], time, .posted-on, span[data-test="job-pubilshed-date"]');

                // Client info - Enhanced selectors
                // Rating: Look in multiple places
                let rating = '';
                const ratingSelectors = [
                    '[data-test="client-rating"] .air3-rating-value-text',
                    '[data-test="rating"] .rating-value',
                    '.air3-rating-value-text',
                    '[data-test="buyer-rating"]',
                    '.rating .value',
                    '[aria-label*="rating"]'
                ];
                for (const sel of ratingSelectors) {
                    const el = card.querySelector(sel);
                    if (el && el.innerText.trim()) {
                        rating = el.innerText.trim();
                        break;
                    }
                }

                // Total spent: Look for money amounts near "spent"
                let spent = '';
                const spentSelectors = [
                    '[data-test="total-spent"]',
                    '[data-test="client-total-spent"]',
                    '[data-test="buyer-spend"]',
                    '.client-spent',
                    '[data-test="client-spendings"]'
                ];
                for (const sel of spentSelectors) {
                    const el = card.querySelector(sel);
                    if (el && el.innerText.trim()) {
                        spent = el.innerText.trim();
                        break;
                    }
                }

                // Payment verified
                const verifiedEl = card.querySelector('[data-test="payment-verified"], [data-test="payment-verified-status"], .payment-verified');

                // Client hires
                let hires = '';
                const hiresSelectors = [
                    '[data-test="client-hires"]',
                    '[data-test="total-hires"]',
                    '.client-hires'
                ];
                for (const sel of hiresSelectors) {
                    const el = card.querySelector(sel);
                    if (el && el.innerText.trim()) {
                        hires = el.innerText.trim();
                        break;
                    }
                }

                // Job details
                const experienceEl = card.querySelector('[data-test="experience-level"], [data-test="contractor-tier"], [data-test="expertise-level"], .experience-level');
                const durationEl = card.querySelector('[data-test="duration"], [data-test="duration-label"], [data-test="engagement-duration"], .duration');
                const hoursEl = card.querySelector('[data-test="workload"], [data-test="hours-per-week"], .weekly-hours');
                const jobTypeEl = card.querySelector('[data-test="job-type"], [data-test="engagement-type"], .job-type');

                // Skills/tags - enhanced
                const skillEls = card.querySelectorAll('[data-test="token"], [data-test="skill"], .air3-token, .skill-badge, [data-test="attr-item"]');
                const skills = Array.from(skillEls).map(s => s.innerText.trim()).filter(s => s.length > 0 && s.length < 50);

                // Proposals count
                let proposals = '';
                const proposalsEl = card.querySelector('[data-test="proposals"], [data-test="proposals-count"], .proposals-count');
                if (proposalsEl) proposals = proposalsEl.innerText.trim();

                // Get full card text for regex fallbacks
                const cardText = card.innerText;

                return {
                    title: titleEl ? titleEl.innerText.trim() : '',
                    url: titleEl ? titleEl.href : '',
                    description: descEl ? descEl.innerText.trim() : '',
                    budget: budgetEl ? budgetEl.innerText.trim() : '',
                    hourlyRate: hourlyEl ? hourlyEl.innerText.trim() : '',
                    fixedPrice: fixedEl ? fixedEl.innerText.trim() : '',
                    location: locationEl ? locationEl.innerText.trim() : '',
                    posted: timeEl ? timeEl.innerText.trim() : '',
                    rating: rating,
                    spent: spent,
                    hires: hires,
                    verified: verifiedEl ? true : false,
                    experience: experienceEl ? experienceEl.innerText.trim() : '',
                    duration: durationEl ? durationEl.innerText.trim() : '',
                    hours: hoursEl ? hoursEl.innerText.trim() : '',
                    jobType: jobTypeEl ? jobTypeEl.innerText.trim() : '',
                    skills: skills,
                    proposals: proposals,
                    cardText: cardText
                };
            });
            JSON.stringify(result);
        """
        import json
        try:
            result = await page.evaluate(script)
            result = str(result) if result else "[]"
            job_data = json.loads(result)
        except Exception as e:
            logger.error(f"Failed to extract jobs: {e}")
            job_data = []

        for data in job_data:
            if not data['title']:
                continue

            # Isolate per-job parsing so one malformed card can't kill the whole page.
            try:
                job_obj = self._build_job(data, keywords)
                if job_obj:
                    jobs.append(job_obj)
            except Exception as e:
                logger.warning(f"Skipping malformed job card ({data.get('title','?')[:40]}): {e}")
            continue

        return jobs

    def _build_job(self, data, keywords):
        """Turn one raw card dict into a JobCreate. May raise on bad input."""
        upwork_id = self._extract_job_id(data['url'])
        card_text = data.get('cardText', '')

        # Parse budget - try multiple sources
        budget_str = data.get('budget') or data.get('hourlyRate') or data.get('fixedPrice') or ''
        budget_type, budget_min, budget_max = self._parse_budget(budget_str)
        if not budget_type:
            budget_type, budget_min, budget_max = self._parse_budget(card_text)

        # Parse client rating - try direct value then regex from card
        client_rating = None
        rating_str = data.get('rating', '')
        if rating_str:
            try:
                # Clean and parse rating like "4.95" or "5.0"
                rating_clean = re.search(r'(\d+\.?\d*)', rating_str)
                if rating_clean:
                    val = rating_clean.group(1)
                    # Reject "." or ".9" — need at least one digit before optional decimal
                    if re.match(r'^\d', val):
                        client_rating = float(val)
            except Exception:
                pass
        if not client_rating:
            client_rating = self._extract_rating(card_text)

        # Parse total spent - direct or from card text
        client_spent = data.get('spent') or self._extract_spent(card_text)

        # Parse client hires
        client_hires = None
        hires_str = data.get('hires', '')
        if hires_str:
            hires_match = re.search(r'(\d+)', hires_str)
            if hires_match:
                client_hires = int(hires_match.group(1))
        if not client_hires:
            client_hires = self._extract_hires(card_text)

        # Parse experience level
        experience = data.get('experience') or self._extract_experience(card_text)

        # Parse duration
        duration = data.get('duration') or self._extract_duration(card_text)

        # Parse job type
        job_type = data.get('jobType') or self._extract_job_type(card_text)

        # Skills - use extracted or fallback to keywords
        skills = data.get('skills') or []
        if not skills:
            skills = keywords

        return JobCreate(
            upwork_id=upwork_id,
            title=data['title'],
            description=data['description'],
            url=data['url'],
            client_country=data.get('location') or None,
            client_rating=client_rating,
            client_total_spent=client_spent,
            client_hires=client_hires,
            budget_type=budget_type,
            budget_min=budget_min,
            budget_max=budget_max,
            experience_level=experience,
            duration=duration,
            job_type=job_type,
            search_keywords=skills,
            posted_at=self._parse_relative_time(data.get('posted', ''))
        )

    def _extract_job_id(self, url: str) -> str:
        """Extract job ID from Upwork URL."""
        if not url:
            return f"unknown_{random.randint(10000, 99999)}"
        match = re.search(r'/jobs/~(\w+)', url)
        if match:
            return match.group(1)
        match = re.search(r'_~(\w+)', url)
        if match:
            return match.group(1)
        return url.split('/')[-1].split('?')[0].replace('~', '')

    def _extract_spent(self, text: str) -> Optional[str]:
        """Extract client total spent from text."""
        patterns = [
            r'(\$[\d,.]+[KMB]?\+?\s*spent)',
            r'(\$[\d,.]+[KMB]?\+?)\s+spent',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_experience(self, text: str) -> Optional[str]:
        """Extract experience level from text."""
        levels = ['Entry Level', 'Intermediate', 'Expert']
        for level in levels:
            if level.lower() in text.lower():
                return level
        return None

    def _extract_duration(self, text: str) -> Optional[str]:
        """Extract estimated duration from text."""
        patterns = [
            r'((?:Less than|More than)?\s*\d+\s*(?:to\s*\d+\s*)?(?:month|week|hour|day)s?)',
            r'(Est\.?\s*(?:time|duration)[:\s]+[^,\n]+)',
            r'(1-3 months|3-6 months|More than 6 months|Less than 1 month)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_rating(self, text: str) -> Optional[float]:
        """Extract client rating from text."""
        patterns = [
            r'(\d\.\d{1,2})\s*(?:of\s*5|stars?|rating)',
            r'rating[:\s]*(\d\.\d{1,2})',
            r'(\d\.\d{1,2})\s*/\s*5',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except:
                    pass
        return None

    def _extract_hires(self, text: str) -> Optional[int]:
        """Extract client hires count from text."""
        patterns = [
            r'(\d+)\s*(?:hires?|hired|freelancers?\s*hired)',
            r'hired\s*(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except:
                    pass
        return None

    def _extract_job_type(self, text: str) -> Optional[str]:
        """Extract job type from text."""
        types = {
            'ongoing': 'Ongoing',
            'one-time': 'One-time',
            'one time': 'One-time',
            'contract': 'Contract',
            'full-time': 'Full-time',
            'full time': 'Full-time',
            'part-time': 'Part-time',
            'part time': 'Part-time',
        }
        text_lower = text.lower()
        for key, value in types.items():
            if key in text_lower:
                return value
        return None

    def _extract_hours(self, text: str) -> Optional[str]:
        """Extract hours per week from text."""
        patterns = [
            r'(\d+(?:\s*-\s*\d+)?)\s*(?:hrs?|hours?)\s*(?:\/|\s*per\s*)\s*(?:wk|week)',
            r'(Less than \d+ hrs\/week|More than \d+ hrs\/week)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_proposals(self, text: str) -> Optional[int]:
        """Extract proposal count from text."""
        patterns = [
            r'(\d+)\s*(?:proposals?|applicants?)',
            r'proposals?[:\s]*(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except:
                    pass
        return None

    def _parse_budget(self, budget_text: str) -> tuple:
        """Parse budget string. Returns (type, min, max) or (None, None, None).

        Defensive: bad matches like '.' or ',' would raise from float(), so we
        wrap parses in a helper that returns None on any conversion failure.
        """
        if not budget_text:
            return None, None, None

        def _num(s: str):
            try:
                v = s.replace(',', '').strip('.')
                if not v or not re.search(r'\d', v):
                    return None
                return float(v)
            except (ValueError, AttributeError):
                return None

        hourly = re.search(r'\$?([\d,.]+)\s*-\s*\$?([\d,.]+)\s*/\s*hr', budget_text, re.I)
        if hourly:
            lo, hi = _num(hourly.group(1)), _num(hourly.group(2))
            if lo is not None and hi is not None:
                return 'hourly', lo, hi
        fixed = re.search(r'\$?([\d,.]+)', budget_text)
        if fixed and 'fixed' in budget_text.lower():
            v = _num(fixed.group(1))
            if v is not None:
                return 'fixed', v, None
        return None, None, None

    def _parse_relative_time(self, time_str: str) -> Optional[datetime]:
        """Parse relative time string."""
        if not time_str:
            return None
        now = datetime.now()
        time_str = time_str.lower()
        patterns = [
            (r'(\d+)\s*minute', 'minutes'),
            (r'(\d+)\s*hour', 'hours'),
            (r'(\d+)\s*day', 'days'),
            (r'(\d+)\s*week', 'weeks'),
        ]
        for pattern, unit in patterns:
            match = re.search(pattern, time_str)
            if match:
                from datetime import timedelta
                value = int(match.group(1))
                if unit == 'minutes':
                    return now - timedelta(minutes=value)
                elif unit == 'hours':
                    return now - timedelta(hours=value)
                elif unit == 'days':
                    return now - timedelta(days=value)
                elif unit == 'weeks':
                    return now - timedelta(weeks=value)
        return now

    async def _go_to_next_page(self, page, current_page: int) -> bool:
        """Navigate to next page.

        `current_page` is the zero-based index of the page we just scraped
        (0 = the first page). The next page number for Upwork's URL is
        therefore current_page + 2 (Upwork uses 1-based pagination and
        page 1 is the bare URL with no ?page param).
        """
        try:
            current_url = await page.evaluate("window.location.href")
            current_url = str(current_url)

            next_page = current_page + 2  # 0-index → next 1-based Upwork page

            if 'page=' in current_url:
                # Replace the existing page=N (both branches now use next_page)
                new_url = re.sub(r'page=\d+', f'page={next_page}', current_url)
            else:
                separator = '&' if '?' in current_url else '?'
                new_url = f"{current_url}{separator}page={next_page}"

            logger.info(f"Navigating to page {next_page}: {new_url}")
            await page.get(new_url)
            await asyncio.sleep(5)
            return True
        except Exception as e:
            logger.error(f"Could not go to next page: {e}")
        return False


nodriver_scraper = NodriverScraper()
