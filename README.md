<p align="center">
  <img src="./docs/social-preview.png" alt="Lead Hunter — Signal Terminal for Upwork intelligence" width="100%"/>
</p>

# Lead Hunter

**AI-powered Upwork intelligence — surface high-signal job posts, enrich the clients, generate proposals.**

Lead Hunter scrapes Upwork search results, detects real company names in job descriptions (filtering out the ocean of tech names and buzzwords), pulls contact info for the companies it finds, and drafts personalised proposals with AI. It runs entirely on your machine.

---

## What it does

- **Scrapes Upwork** using an undetected Chrome instance that clears Cloudflare with a saved session
- **Detects real company names** with a strict pattern + evidence detector (rejects `LLMs`, `RAG`, `AI Agents`, `Your Experience`, and 200+ other false-positive shapes)
- **Enriches leads** — walks Bing → the company's official site → contact page, pulling emails, phones, social profiles
- **Scores every job** on client history, budget, company confidence — surfaces the top matches as "Hot Leads"
- **Generates full proposals** (cover letter, why-you-fit, approach, timeline, smart questions) via Groq / LLaMA 3.3
- **UI-driven config** — connect Upwork, manage API keys, and switch backend URLs without touching `.env`

---

## Quick start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Google Chrome installed (for the scraper)
- A free [Groq API key](https://console.groq.com) for AI features (optional but recommended)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate           # Windows
# source venv/bin/activate      # macOS / Linux
pip install -r requirements.txt
cp .env.example .env             # optional — everything is also editable via the UI
python run.py
```

Backend serves on **http://localhost:8500**. API docs at `/api/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend serves on **http://localhost:3500**.

---

## First run

1. Open **http://localhost:3500**
2. Go to the **Settings** tab, paste your Groq API key, click *Test connection*
3. Click the **Connected** dropdown in the header → **Connect to Upwork** — a Chrome window opens
4. Complete any Cloudflare challenge, log in if needed, click **Save Session**
5. In the **Profile** tab, describe what you do — the AI generates search keywords for you
6. Go to **Signal**, hit *Run*, wait ~1 minute per 10 pages of results
7. Toggle *Company signals only* to see the jobs worth applying to
8. Click ✨ on any hot lead to generate a full proposal

---

## Architecture

```
backend/
  app/
    api/
      routes/            REST endpoints
        jobs.py             CRUD + search
        ai.py               AI features (proposals, scoring, enrichment)
        session.py          UI-driven Upwork auth
        settings.py         Runtime settings (API keys, model, etc.)
      scrapers/
        nodriver_scraper.py Upwork search scraper (undetected Chrome + saved cookies)
      services/
        job_service.py         persistence + orchestration
        ai_service.py          Groq / LLaMA integration
        enrichment_service.py  Bing search + website contact scraping
        session_service.py     Upwork session lifecycle
        settings_service.py    DB-backed config (overrides env vars)
      detectors/
        company_detector.py    strict pattern-based company detection
    core/
      config.py         env-based defaults
      database.py       SQLAlchemy setup
    models/job.py       ORM models
    schemas/job.py      Pydantic schemas
    main.py             FastAPI app + CORS + rate limiting

frontend/
  src/
    app/                Next.js App Router
    components/         React UI (SearchSection, LeadsSection, etc.)
    lib/
      api.ts            typed API client (backend URL configurable via UI)
      types.ts          shared TypeScript types
```

---

## Features in detail

### Company detection
The detector uses ~10 tightly-scoped patterns (`we are X`, `at X, we`, `X Inc./LLC`, `About X:`, explicit domain mentions) and only fires above a `0.60` confidence threshold. Every candidate is filtered against a 200-entry blocklist of tech names, common English words, and pronouns.

### Proposal generation
Three tones (Professional / Friendly / Enthusiastic). Uses your saved profile + the specific job to produce:
- **Cover letter** — 2-3 paragraphs referencing the actual job
- **Why I'm the right fit** — matches your skills to their requirements
- **Approach** — how you'd tackle the project
- **Timeline** — realistic estimate
- **Smart questions** — 2-3 questions that show you thought about it

### UI-first configuration
- Backend URL, Groq key, model, and headless mode are all editable in the **Settings** tab
- Values persist to a local SQLite DB and take effect immediately (no restart)
- Env vars still work as fallbacks for a fresh install

### Session management
No terminal commands for Upwork auth. The Connect flow opens a real Chrome window, waits for you to clear Cloudflare and log in, then captures the cookies and hands them to the scraper.

---

## Configuration

Everything is UI-configurable, but if you prefer `.env`:

```bash
# backend/.env
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./upwork_jobs.db
GROQ_API_KEY=gsk_...           # optional — falls back to basic keyword extraction
GROQ_MODEL=llama-3.3-70b-versatile
SCRAPER_HEADLESS=false          # false is more reliable against Cloudflare
```

Frontend picks up the backend URL from (in order): `localStorage["apiBaseUrl"]` → `NEXT_PUBLIC_API_URL` → `http://localhost:8500/api`.

---

## API

Full OpenAPI spec at `http://localhost:8500/api/docs`. Highlights:

| Method | Path | Description |
|-------:|------|-------------|
| POST | `/api/jobs/search` | Scrape Upwork with configurable depth (1-100 pages) |
| GET  | `/api/jobs` | List jobs (paginated, filterable by company mention) |
| POST | `/api/ai/proposal/{job_id}` | Generate full proposal with tone selector |
| POST | `/api/ai/enrich/{job_id}` | Kick off contact-info enrichment |
| GET  | `/api/ai/recommendations` | Hot Leads + Fresh Opportunities |
| POST | `/api/session/connect` | Open browser for Upwork auth |
| POST | `/api/session/save` | Persist cookies after auth |
| GET  | `/api/settings` | List all runtime settings |
| PUT  | `/api/settings/{key}` | Update a setting (takes effect immediately) |

---

## Tech stack

**Backend** — Python 3.11, FastAPI, SQLAlchemy (async), SQLite, nodriver, Groq SDK, loguru
**Frontend** — Next.js 16, React 19, TypeScript, TailwindCSS 4, TanStack Query, Zustand

---

## Author

Built by **UJ** — [ujdeveloper@outlook.com](mailto:ujdeveloper@outlook.com)

---

## License

MIT — see [LICENSE](./LICENSE).
