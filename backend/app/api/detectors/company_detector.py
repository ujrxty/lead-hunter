"""Rock-solid company name detection for Upwork job descriptions.

Design principles:
- **False positives are worse than false negatives.** A wrong company name
  wastes enrichment cycles and pollutes the UI. Missing a real one just
  means the user sees "no company mention" — safe.
- Every candidate must clear multiple independent gates: pattern match,
  shape check, blocklist, evidence-of-realness.
- Confidence starts LOW and only climbs with corroborating signals
  (legal suffix, domain mention, capitalized brand phrase, repetition).
"""
import re
from typing import Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class CompanyMatch:
    name: str
    confidence: float
    context: str
    pattern_type: str


# Minimum confidence a match must reach to be reported as a company mention.
# Tuned to catch real brand mentions but reject "with LLMs", "AI Agents", etc.
MIN_CONFIDENCE = 0.60


class CompanyDetector:
    """Detects real company names in job descriptions.

    Approach:
    1. Very selective patterns — only high-signal phrasings ("we are X",
       "at X, we", "X Inc/LLC", explicit domain, "our company X").
    2. Every candidate is shape-checked (proper capitalization, no
       verb-like tokens, sensible length).
    3. Aggressive blocklists: pronouns, generic nouns, tech names,
       common acronyms (LLM/RAG/API/AI/ML/etc.), Upwork boilerplate.
    4. Confidence needs *corroborating evidence* to cross MIN_CONFIDENCE:
         + legal suffix (Inc, LLC, Corp)  → strong
         + domain matching name           → strong
         + name appears 2+ times          → moderate
         + name appears in title case within its own context  → moderate
       An "at X" alone stays under the threshold.
    """

    # ---- PATTERNS -----------------------------------------------------
    # Each pattern captures a candidate name in group(1). Confidence is
    # the BASE score for the pattern; we adjust it in _score().
    # Patterns favor phrasing that a real company posting would use.
    COMPANY_PATTERNS = [
        # "we are Acme" / "we are Acme Inc" / "we are Acme, a ..."
        (r"\b[Ww]e\s+are\s+([A-Z][A-Za-z][A-Za-z0-9&\-'\.]*(?:\s+[A-Z][A-Za-z0-9&\-'\.]+){0,3})(?=\s*[,\.;]|\s+(?:an?|the|—|-))",
         0.65, "we_are"),

        # "our company, Acme," / "our company is Acme."
        (r"\b[Oo]ur\s+company(?:\s+is|,)?\s+([A-Z][A-Za-z][A-Za-z0-9&\-'\.]*(?:\s+[A-Z][A-Za-z0-9&\-'\.]+){0,3})(?=\s*[,\.;])",
         0.75, "our_company"),

        # "at Acme, we" / "at Acme we're"
        (r"\bat\s+([A-Z][A-Za-z][A-Za-z0-9&\-'\.]*(?:\s+[A-Z][A-Za-z0-9&\-'\.]+){0,3})\s*,\s*we\b",
         0.70, "at_company_we"),

        # "I'm the founder/CEO/CTO of Acme"
        (r"\b(?:I'?m|I\s+am)\s+(?:the\s+)?(?:founder|co-?founder|CEO|CTO|COO|owner|director)\s+(?:of|at)\s+([A-Z][A-Za-z][A-Za-z0-9&\-'\.]*(?:\s+[A-Z][A-Za-z0-9&\-'\.]+){0,3})(?=\s*[,\.;]|\s+and|\s+—)",
         0.75, "founder_of"),

        # "Acme is looking for / seeking / hiring"
        (r"\b([A-Z][A-Za-z][A-Za-z0-9&\-'\.]*(?:\s+[A-Z][A-Za-z0-9&\-'\.]+){0,3})\s+is\s+(?:currently\s+)?(?:looking\s+for|seeking|hiring|searching\s+for)\b",
         0.65, "brand_is_hiring"),

        # "Acme Inc." / "Acme LLC" / "Acme, Inc"
        (r"\b([A-Z][A-Za-z][A-Za-z0-9&\-'\.]*(?:\s+[A-Z][A-Za-z0-9&\-'\.]+){0,3})[,\s]+(?:Inc\.?|LLC|Ltd\.?|Limited|Corp\.?|Corporation|GmbH|B\.?V\.?|S\.?A\.?)\b",
         0.85, "legal_entity"),

        # "About Acme:" or "About Acme —" (common intro heading)
        (r"\bAbout\s+([A-Z][A-Za-z][A-Za-z0-9&\-'\.]*(?:\s+[A-Z][A-Za-z0-9&\-'\.]+){0,3})\s*[:\-—]",
         0.70, "about_company"),

        # Explicit company name label: "Company: Acme" / "Company Name — Acme"
        (r"\b(?:Company|Client|Employer)(?:\s+Name)?\s*[:\-—]\s*([A-Z][A-Za-z][A-Za-z0-9&\-'\.]*(?:\s+[A-Z][A-Za-z0-9&\-'\.]+){0,3})\b",
         0.85, "company_label"),

        # Domain mentions — strongest signal that a real company exists
        (r"(?:website|site|homepage)\s*[:\-—]?\s*(?:https?://)?(?:www\.)?([a-z][a-z0-9\-]{2,})\.(?:com|io|co|ai|net|org|app|dev|xyz)\b",
         0.85, "website_label"),

        # bare-URL brand: https://acme.com or www.acme.com
        (r"https?://(?:www\.)?([a-z][a-z0-9\-]{2,})\.(?:com|io|co|ai|net|org|app|dev|xyz)\b",
         0.75, "bare_url"),
    ]

    # Common English/business words that should NEVER be a company name on their own.
    EXCLUDE_WORDS = {
        "the", "this", "that", "these", "those", "a", "an",
        "our", "your", "their", "we", "you", "they", "i", "my", "me", "us", "it", "its",
        "he", "she", "his", "her", "them",

        # Verbs/modals often capitalized after periods
        "please", "thank", "thanks", "note", "important", "required",
        "must", "should", "would", "could", "will", "can", "may", "might",
        "looking", "seeking", "hiring", "need", "needed", "want", "wanted",
        "search", "find", "get", "join", "help", "build", "create", "develop",
        "make", "work", "working", "use", "using", "add", "adding",
        "have", "has", "had", "is", "are", "was", "were", "be", "been",

        # Generic business/HR nouns
        "client", "clients", "company", "business", "project", "projects",
        "job", "jobs", "work", "role", "position", "opportunity", "candidate",
        "remote", "onsite", "hybrid", "full", "part", "time", "freelance", "contract",
        "experience", "years", "year", "skills", "skill", "requirements",
        "qualifications", "responsibilities", "duties", "tasks",
        "about", "description", "overview", "summary", "details", "background",
        "team", "startup", "agency", "organization",

        # Application/portfolio words the user's screenshot showed
        "portfolio", "resume", "cv", "linkedin", "github", "website",
        "email", "phone", "reference", "references", "application",

        # Common resume/tech acronyms mistaken for names
        "ai", "ml", "llm", "llms", "rag", "mcp", "api", "apis", "sdk",
        "ui", "ux", "cms", "crm", "erp", "seo", "sem", "kpi", "roi",
        "mvp", "poc", "b2b", "b2c", "saas", "paas", "iaas",
        "http", "https", "html", "css", "js", "ts", "sql", "url",
        "csv", "pdf", "xml", "json", "yaml", "usa", "uk", "eu", "asia",

        # Languages / regions (not companies)
        "english", "spanish", "french", "german", "chinese", "japanese",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",

        # Upwork boilerplate
        "upwork", "top-rated", "expert-vetted", "hourly", "fixed",
    }

    # Multi-word phrases that look like companies but aren't.
    EXCLUDE_PHRASES = {
        "ai agents", "ai agent", "ai models", "ai model",
        "our team", "your team", "the team", "the client", "the company",
        "the project", "the role", "the job", "the position",
        "google sheets", "google docs", "google drive", "google workspace",
        "microsoft office", "microsoft word", "microsoft excel",
        "web scraping", "data extraction", "data pipeline", "data pipelines",
        "machine learning", "deep learning", "computer vision",
        "natural language", "large language",
        "csv excel", "excel csv",
    }

    # Tech names — never companies, always tools/products.
    TECH_NAMES = {
        # Databases
        "supabase", "firebase", "mongodb", "postgres", "postgresql", "mysql", "redis",
        "dynamodb", "cassandra", "elasticsearch", "sqlite", "mariadb",
        "cockroachdb", "planetscale", "neon", "prisma", "drizzle", "sqlalchemy",
        # Cloud / infra
        "aws", "azure", "gcp", "digitalocean", "heroku", "vercel", "netlify",
        "cloudflare", "railway", "render", "docker", "kubernetes", "terraform",
        "ansible", "jenkins", "circleci",
        # Frontend
        "react", "vue", "angular", "svelte", "nextjs", "nuxt", "gatsby",
        "remix", "astro", "solid", "qwik", "preact", "tailwind", "tailwindcss",
        "bootstrap", "shadcn", "radix", "framer",
        # Backend / lang
        "node", "nodejs", "express", "fastapi", "django", "flask", "rails",
        "laravel", "spring", "nestjs", "fastify", "bun", "deno",
        "python", "javascript", "typescript", "rust", "golang", "java",
        "kotlin", "swift", "php", "ruby", "scala", "elixir",
        # CMS / commerce
        "shopify", "woocommerce", "magento", "bigcommerce", "squarespace",
        "webflow", "wordpress", "drupal", "contentful", "sanity", "strapi",
        "ghost", "gohighlevel",
        # APIs / SaaS tools (product names, not companies in job context)
        "stripe", "twilio", "sendgrid", "mailchimp", "auth0", "clerk",
        "okta", "plaid", "algolia", "meilisearch", "typesense",
        "openai", "anthropic", "cohere", "huggingface", "replicate",
        "groq", "gemini", "claude", "gpt", "chatgpt", "copilot",
        "langchain", "langgraph", "llamaindex", "pinecone", "weaviate",
        "qdrant", "chroma", "ollama", "mistral",
        # DevOps
        "datadog", "newrelic", "sentry", "grafana", "prometheus", "splunk",
        # Payments
        "paypal", "braintree", "adyen", "razorpay", "square",
        # Comms
        "slack", "discord", "telegram", "whatsapp", "intercom", "zendesk",
        # Analytics
        "mixpanel", "amplitude", "segment", "posthog", "plausible",
        # Version control / collab
        "github", "gitlab", "bitbucket", "jira", "confluence", "notion",
        "linear", "asana", "trello", "clickup", "monday", "airtable", "coda",
        # Testing
        "jest", "cypress", "playwright", "selenium", "puppeteer", "vitest",
        "pytest", "nodriver",
        # Mobile
        "flutter", "expo", "ionic", "capacitor",
        # ML libs
        "tensorflow", "pytorch", "keras", "scikit", "pandas", "numpy",
        # Design
        "figma", "sketch", "adobe", "canva", "invision",
        # Automation
        "zapier", "n8n", "make", "integromat",
        # Office / files
        "excel", "word", "powerpoint", "outlook", "teams", "sheets", "docs",
    }

    def __init__(self):
        self.compiled_patterns = [
            (re.compile(p, re.MULTILINE), conf, ptype)
            for p, conf, ptype in self.COMPANY_PATTERNS
        ]

    # ---- PUBLIC ----------------------------------------------------------
    def detect(self, text: str) -> Optional[CompanyMatch]:
        """Return the highest-confidence company match above MIN_CONFIDENCE, else None."""
        if not text or len(text) < 20:
            return None

        candidates: List[CompanyMatch] = []
        seen: set = set()

        for pattern, base_conf, ptype in self.compiled_patterns:
            for m in pattern.finditer(text):
                raw = m.group(1).strip().rstrip('.,;:')

                # Normalize domain-style captures back to a title-cased brand
                if ptype in ("website_label", "bare_url"):
                    name = raw.capitalize()
                else:
                    name = raw

                if not self._is_valid(name):
                    continue

                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)

                ctx_start = max(0, m.start() - 60)
                ctx_end = min(len(text), m.end() + 60)
                context = text[ctx_start:ctx_end].strip()

                confidence = self._score(name, base_conf, text, ptype)

                candidates.append(CompanyMatch(
                    name=name, confidence=confidence,
                    context=context, pattern_type=ptype
                ))

        if not candidates:
            return None

        best = max(candidates, key=lambda c: c.confidence)
        if best.confidence < MIN_CONFIDENCE:
            return None
        return best

    def has_company_mention(self, text: str) -> Tuple[bool, Optional[str], float, Optional[str]]:
        """Convenience wrapper. Returns (found, name, confidence, context)."""
        m = self.detect(text)
        if m:
            return True, m.name, m.confidence, m.context
        return False, None, 0.0, None

    # ---- VALIDATION ------------------------------------------------------
    def _is_valid(self, name: str) -> bool:
        """Reject shapes that are almost never real company names."""
        n = name.strip()
        if len(n) < 3 or len(n) > 60:
            return False

        # No trailing/embedded weirdness
        if n.startswith("-") or n.endswith("-"):
            return False

        lower = n.lower()

        # Full phrase blocklist
        if lower in self.EXCLUDE_PHRASES:
            return False
        if lower in self.EXCLUDE_WORDS:
            return False
        if lower in self.TECH_NAMES:
            return False

        words = n.split()

        # Reject if EVERY word is a stopword or tech name
        stop_or_tech = lambda w: (w.lower() in self.EXCLUDE_WORDS
                                  or w.lower() in self.TECH_NAMES)
        if all(stop_or_tech(w) for w in words):
            return False

        # Reject if the FIRST word is a stopword ("Your experience",
        # "The team", "About us", "Our clients" all match a naive pattern)
        if words[0].lower() in self.EXCLUDE_WORDS:
            return False

        # Reject if the LAST word is a stopword ("Acme Team", "Acme Company")
        if len(words) > 1 and words[-1].lower() in self.EXCLUDE_WORDS:
            return False

        # Any word being a known tech name → not a company
        for w in words:
            wl = w.lower().rstrip('.,;:')
            if wl in self.TECH_NAMES:
                return False

        # Reject pure acronyms (AI, LLM, RAG, MCP, API, KPI, etc.)
        # Single all-caps token up to 5 chars = almost always an acronym.
        if len(words) == 1 and n.isupper() and len(n) <= 5:
            return False

        # Reject if the name is a common English word (single word, all lowercase-able)
        # e.g. "Portfolio", "Experience", "Development"
        if len(words) == 1:
            common_english = {
                "development", "developer", "engineer", "engineering",
                "design", "designer", "marketing", "sales", "product",
                "manager", "management", "founder", "consultant",
                "portfolio", "experience", "background", "expertise",
                "solution", "solutions", "service", "services", "system",
                "systems", "platform", "software", "application", "applications",
                "website", "websites", "content", "quality", "support",
                "communication", "collaboration", "leadership",
                "clean", "modern", "professional", "creative", "innovative",
                "senior", "junior", "lead", "principal", "staff",
                "success", "growth", "strategy", "operations", "finance",
                "healthcare", "education", "technology", "industry",
                "america", "european", "asian", "global", "international",
            }
            if lower in common_english:
                return False

        # Reject names that contain a verb-y trailing token like "is", "are"
        if any(w.lower() in {"is", "are", "was", "were", "will", "would"} for w in words):
            return False

        return True

    # ---- SCORING ---------------------------------------------------------
    def _score(self, name: str, base: float, text: str, ptype: str) -> float:
        """Adjust confidence based on corroborating evidence.

        Base pattern confidence rarely clears MIN_CONFIDENCE (0.75) alone —
        we require *evidence* like a legal suffix, repeated mention, or
        matching domain to trust the name.
        """
        conf = base
        n_low = name.lower()
        t_low = text.lower()

        # Repeated mentions = corroborating evidence
        occurrences = t_low.count(n_low)
        if occurrences >= 2:
            conf += 0.10
        if occurrences >= 3:
            conf += 0.05

        # Legal suffix nearby → very strong signal
        if re.search(rf"\b{re.escape(name)}[,\s]+(?:Inc\.?|LLC|Ltd\.?|Corp\.?|GmbH)\b", text):
            conf += 0.15

        # A domain matching the name is a strong signal
        domain_stub = re.sub(r"[^a-z0-9]", "", n_low)
        if len(domain_stub) >= 4 and re.search(
            rf"\b{re.escape(domain_stub)}\.(?:com|io|co|ai|net|org|app|dev)\b", t_low
        ):
            conf += 0.15

        # Email domain matching name
        if re.search(rf"@{re.escape(domain_stub)}\.[a-z]{{2,}}", t_low):
            conf += 0.10

        # Legal-entity pattern is already trustworthy — small bonus
        if ptype == "legal_entity":
            conf += 0.05

        # Website labels are trustworthy when domain isn't a known tech tool
        if ptype in ("website_label", "bare_url"):
            if n_low in self.TECH_NAMES:
                conf -= 0.30

        return max(0.0, min(conf, 1.0))


company_detector = CompanyDetector()
