"""Lead Enrichment Service - Finds contact info for companies."""
import asyncio
import re
import json
from typing import Dict, List, Optional
from urllib.parse import urlparse, quote_plus
from loguru import logger

try:
    import nodriver as uc
except ImportError:
    uc = None


class EnrichmentService:
    """Service for enriching leads with contact information."""

    def __init__(self):
        self.browser = None

    async def _get_browser(self):
        if not uc:
            raise RuntimeError("nodriver not installed")
        if not self.browser:
            from app.core.config import settings
            self.browser = await uc.start(
                headless=settings.scraper_headless,
                browser_args=['--window-position=-2000,-2000']
            )
        return self.browser

    async def _close_browser(self):
        if self.browser:
            try:
                self.browser.stop()
            except:
                pass
            self.browser = None

    async def enrich_company(self, company_name: str) -> Dict:
        """Enrich a company with contact information."""
        logger.info(f"Starting enrichment for: {company_name}")

        result = {
            "company_name": company_name,
            "website": None,
            "emails": [],
            "phones": [],
            "linkedin": None,
            "twitter": None,
            "instagram": None,
            "facebook": None,
            "address": None,
            "description": None
        }

        try:
            browser = await self._get_browser()

            # Search for company website and contact info
            search_results = await self._search_company(browser, company_name)
            logger.info(f"Search returned {len(search_results)} results")

            if not search_results:
                # Try alternative search
                search_results = await self._search_company(browser, f"{company_name} company website")
                logger.info(f"Alternative search returned {len(search_results)} results")

            # Find official website
            website = self._find_official_website(search_results, company_name)
            if website:
                result["website"] = website
                logger.info(f"Found website: {website}")

                # Scrape website for contact info
                try:
                    contact_info = await self._scrape_website(browser, website)
                    if contact_info.get("emails"):
                        result["emails"] = contact_info["emails"]
                    if contact_info.get("phones"):
                        result["phones"] = contact_info["phones"]
                    if contact_info.get("description"):
                        result["description"] = contact_info["description"]
                    logger.info(f"Scraped: {len(result['emails'])} emails, {len(result['phones'])} phones")
                except Exception as e:
                    logger.warning(f"Website scrape failed: {e}")

            # Extract social profiles
            socials = self._extract_social_profiles(search_results)
            result.update(socials)
            logger.info(f"Social profiles: {[k for k, v in socials.items() if v]}")

        except Exception as e:
            logger.error(f"Enrichment error: {e}")
        finally:
            await self._close_browser()

        return result

    async def _search_company(self, browser, query: str) -> List[Dict]:
        """Search for a company. Bing is the primary engine (scrape-friendly);
        DuckDuckGo Lite is a fallback. Bing wraps result URLs in redirect links,
        so we decode the base64 `u` param client-side."""
        results = await self._search_bing(browser, query)
        if not results:
            results = await self._search_ddg_lite(browser, query)
        return results

    async def _search_bing(self, browser, query: str) -> List[Dict]:
        results: List[Dict] = []
        try:
            search_url = f"https://www.bing.com/search?q={quote_plus(query)}"
            logger.debug(f"Searching Bing: {search_url}")
            page = await browser.get(search_url)
            await asyncio.sleep(2.5)

            script = """
                (() => {
                    const decode = (href) => {
                        try {
                            const u = new URL(href);
                            const p = u.searchParams.get('u');
                            if (p && p.startsWith('a1')) {
                                let b = p.slice(2).replace(/-/g,'+').replace(/_/g,'/');
                                while (b.length % 4) b += '=';
                                return atob(b);
                            }
                        } catch (e) {}
                        return href;
                    };
                    const out = [];
                    document.querySelectorAll('li.b_algo').forEach(li => {
                        const a = li.querySelector('h2 a');
                        if (!a) return;
                        const cite = li.querySelector('cite');
                        const snip = li.querySelector('.b_caption p, .b_algoSlug');
                        let url = decode(a.href);
                        if ((!url || url.includes('bing.com')) && cite) {
                            let c = cite.innerText.trim();
                            if (c && !/^https?:/.test(c)) c = 'https://' + c.split(' ')[0];
                            url = c;
                        }
                        out.push({ url: url, title: a.innerText.trim(), snippet: snip ? snip.innerText.trim() : '' });
                    });
                    return JSON.stringify(out);
                })();
            """
            result = await page.evaluate(script)
            if result:
                results = json.loads(str(result))
            logger.debug(f"Bing found {len(results)} results")
        except Exception as e:
            logger.warning(f"Bing search failed: {e}")
        return results

    async def _search_ddg_lite(self, browser, query: str) -> List[Dict]:
        results: List[Dict] = []
        try:
            search_url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
            logger.debug(f"Searching DDG Lite: {search_url}")
            page = await browser.get(search_url)
            await asyncio.sleep(2)
            script = """
                (() => {
                    const out = [];
                    document.querySelectorAll('a.result-link').forEach(a => {
                        if (a.href) out.push({ url: a.href, title: a.innerText.trim(), snippet: '' });
                    });
                    return JSON.stringify(out);
                })();
            """
            result = await page.evaluate(script)
            if result:
                results = json.loads(str(result))
            logger.debug(f"DDG Lite found {len(results)} results")
        except Exception as e:
            logger.warning(f"DDG Lite search failed: {e}")
        return results

    def _find_official_website(self, results: List[Dict], company_name: str) -> Optional[str]:
        """Find the most likely official website."""
        company_lower = company_name.lower().replace(' ', '').replace('-', '')

        skip_domains = [
            'linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com', 'x.com',
            'crunchbase.com', 'glassdoor.com', 'indeed.com', 'upwork.com',
            'wikipedia.org', 'yelp.com', 'bloomberg.com', 'youtube.com',
            'github.com', 'medium.com', 'reddit.com', 'quora.com',
            'duckduckgo.com', 'google.com', 'bing.com'
        ]

        # Score candidates: prefer domains that actually match the company name.
        # A random top result (like a Microsoft support page) is not a website match.
        scored = []
        for i, result in enumerate(results):
            url = result.get('url', '')
            try:
                domain = urlparse(url).netloc.lower().replace('www.', '')
                if not domain or any(skip in domain for skip in skip_domains):
                    continue

                domain_base = domain.split('.')[0]
                score = 0

                # Strong match: domain base equals company name
                if domain_base == company_lower:
                    score += 100
                # Domain base contains full company name (or vice versa when short)
                elif len(company_lower) >= 5 and company_lower in domain_base:
                    score += 60
                elif len(domain_base) >= 5 and domain_base in company_lower:
                    score += 40
                # Weak match: first 4 chars overlap (only accept if company name is distinctive)
                elif len(company_lower) >= 6 and company_lower[:5] in domain_base:
                    score += 20

                # Small bonus for higher-ranked results
                score += max(0, 10 - i)

                if score >= 20:
                    scored.append((score, url))
            except Exception:
                continue

        if scored:
            scored.sort(reverse=True)
            return scored[0][1]

        # No confident website match — return None rather than a wrong page.
        # This surfaces "no contact info found" in the UI, which is honest.
        return None

    async def _scrape_website(self, browser, url: str) -> Dict:
        """Scrape website for contact information."""
        info = {
            "emails": [],
            "phones": [],
            "description": None
        }

        try:
            page = await browser.get(url)
            await asyncio.sleep(2)

            # Get page text content
            content = await page.evaluate("document.body.innerText || ''")
            content = str(content) if content else ""

            # Get page HTML for href mailto: links
            html = await page.evaluate("document.body.innerHTML || ''")
            html = str(html) if html else ""

            # Extract emails from mailto links first (most reliable)
            mailto_emails = re.findall(r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', html.lower())

            # Extract emails from text
            text_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)

            # Combine and dedupe, prioritize mailto
            all_emails = list(dict.fromkeys(mailto_emails + text_emails))
            # Filter out common non-contact emails
            filtered_emails = [e for e in all_emails if not any(x in e.lower() for x in ['example', 'test', 'noreply', 'no-reply', '@sentry', '@github', 'wixpress'])]
            info["emails"] = filtered_emails[:5]

            # Extract phone numbers with various formats
            phone_patterns = [
                r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',  # US/Canada
                r'\+[0-9]{1,3}[-.\s]?[0-9]{2,4}[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{3,4}',  # International
            ]
            phones = []
            for pattern in phone_patterns:
                matches = re.findall(pattern, content)
                phones.extend(matches)

            # Clean and validate phones
            valid_phones = []
            seen = set()
            for p in phones:
                clean = re.sub(r'\D', '', p)
                if 10 <= len(clean) <= 15 and clean not in seen:
                    seen.add(clean)
                    valid_phones.append(p.strip())
            info["phones"] = valid_phones[:5]

            # Get meta description
            desc = await page.evaluate("""
                (document.querySelector('meta[name="description"]')?.content ||
                 document.querySelector('meta[property="og:description"]')?.content ||
                 '').substring(0, 200)
            """)
            if desc:
                info["description"] = str(desc)

            # If no emails found, try contact page
            if not info["emails"]:
                contact_url = await page.evaluate("""
                    const links = Array.from(document.querySelectorAll('a'));
                    const contact = links.find(a =>
                        a.href &&
                        (a.innerText.toLowerCase().includes('contact') ||
                         a.href.toLowerCase().includes('contact') ||
                         a.innerText.toLowerCase().includes('get in touch'))
                    );
                    contact ? contact.href : null;
                """)

                if contact_url:
                    logger.debug(f"Visiting contact page: {contact_url}")
                    try:
                        await page.get(str(contact_url))
                        await asyncio.sleep(2)

                        contact_html = await page.evaluate("document.body.innerHTML || ''")
                        contact_html = str(contact_html) if contact_html else ""

                        more_emails = re.findall(r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', contact_html.lower())
                        more_emails += re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', contact_html)

                        filtered = [e for e in more_emails if not any(x in e.lower() for x in ['example', 'test', 'noreply', 'no-reply'])]
                        info["emails"] = list(dict.fromkeys(filtered))[:5]
                    except Exception as e:
                        logger.debug(f"Contact page scrape failed: {e}")

        except Exception as e:
            logger.error(f"Website scrape error: {e}")

        return info

    def _extract_social_profiles(self, results: List[Dict]) -> Dict:
        """Extract social media profiles from search results."""
        socials = {
            "linkedin": None,
            "twitter": None,
            "instagram": None,
            "facebook": None
        }

        for result in results:
            url = result.get('url', '')
            url_lower = url.lower()

            if 'linkedin.com/company' in url_lower and not socials["linkedin"]:
                socials["linkedin"] = url
            elif ('twitter.com/' in url_lower or 'x.com/' in url_lower) and not socials["twitter"]:
                socials["twitter"] = url
            elif 'instagram.com/' in url_lower and not socials["instagram"]:
                socials["instagram"] = url
            elif 'facebook.com/' in url_lower and not socials["facebook"]:
                socials["facebook"] = url

        return socials


enrichment_service = EnrichmentService()
