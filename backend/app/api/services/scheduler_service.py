import asyncio
from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import async_session_maker
from app.models.job import SearchQuery, SchedulerRun, Job
from app.schemas.job import SearchRequest, JobCreate
from app.api.scrapers.nodriver_scraper import nodriver_scraper
from app.api.detectors.company_detector import company_detector
from app.api.services.notification_service import notification_service
from app.api.services.settings_service import settings_service


class SchedulerService:
    """Background scheduler for automated job scraping."""

    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._is_running = False
        self._current_run_id: Optional[int] = None
        self._last_run_at: Optional[datetime] = None
        self._next_run_at: Optional[datetime] = None
        self._interval_minutes = 30
        self._delay_between_searches = 3  # seconds between page fetches
        self._max_pages_per_search = 25

    @property
    def is_running(self) -> bool:
        return self._is_running and self._scheduler is not None and self._scheduler.running

    @property
    def status(self) -> dict:
        return {
            "is_running": self.is_running,
            "interval_minutes": self._interval_minutes,
            "last_run_at": self._last_run_at.isoformat() if self._last_run_at else None,
            "next_run_at": self._next_run_at.isoformat() if self._next_run_at else None,
            "delay_between_searches": self._delay_between_searches,
            "max_pages_per_search": self._max_pages_per_search
        }

    async def start(self, interval_minutes: int = None):
        if interval_minutes:
            self._interval_minutes = interval_minutes

        if self._scheduler is None:
            self._scheduler = AsyncIOScheduler()

        if self._scheduler.running:
            logger.info("Scheduler already running")
            return

        self._scheduler.add_job(
            self._run_scheduled_searches,
            IntervalTrigger(minutes=self._interval_minutes),
            id="upwork_scraper",
            replace_existing=True,
            next_run_time=datetime.now()  # run immediately on start
        )

        self._scheduler.start()
        self._is_running = True
        self._update_next_run_time()

        logger.info(f"Scheduler started with {self._interval_minutes} minute interval")
        await notification_service.notify_scheduler_status(
            "started",
            f"Running every {self._interval_minutes} minutes",
            self._next_run_at.isoformat() if self._next_run_at else None
        )

    async def stop(self):
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._is_running = False
            self._next_run_at = None
            logger.info("Scheduler stopped")
            await notification_service.notify_scheduler_status("stopped")

    async def set_interval(self, minutes: int):
        self._interval_minutes = max(1, min(minutes, 1440))  # 1 min to 24 hours

        if self.is_running:
            self._scheduler.reschedule_job(
                "upwork_scraper",
                trigger=IntervalTrigger(minutes=self._interval_minutes)
            )
            self._update_next_run_time()
            logger.info(f"Scheduler interval updated to {self._interval_minutes} minutes")

    def _update_next_run_time(self):
        if self._scheduler and self._scheduler.running:
            job = self._scheduler.get_job("upwork_scraper")
            if job:
                self._next_run_at = job.next_run_time

    async def _run_scheduled_searches(self):
        logger.info("Starting scheduled search run")
        self._last_run_at = datetime.now()
        self._update_next_run_time()

        # Get scheduled queries first
        queries_data = []
        async with async_session_maker() as db:
            try:
                result = await db.execute(
                    select(SearchQuery).where(
                        SearchQuery.is_scheduled == True,
                        SearchQuery.is_active == True
                    )
                )
                queries = result.scalars().all()
                # Extract data before session closes
                for q in queries:
                    queries_data.append({
                        "id": q.id,
                        "name": q.name,
                        "keywords": q.keywords,
                        "search_type": q.search_type,
                        "max_pages": q.max_pages or 5
                    })
            except Exception as e:
                logger.error(f"Failed to fetch queries: {e}")
                await notification_service.notify_error(str(e), context="Fetch queries")
                return

        if not queries_data:
            logger.info("No scheduled queries found")
            return

        total_new = 0
        total_with_company = 0

        for query_info in queries_data:
            try:
                new_jobs, with_company = await self._run_single_search(query_info)
                total_new += new_jobs
                total_with_company += with_company
                # Rate limit between searches
                await asyncio.sleep(self._delay_between_searches)
            except Exception as e:
                logger.error(f"Error running search '{query_info['name']}': {e}")
                await notification_service.notify_error(
                    str(e),
                    context=f"Search: {query_info['name'] or query_info['keywords']}"
                )

        if total_new > 0:
            await notification_service.notify_new_jobs(
                total_new,
                total_with_company,
                f"{len(queries_data)} saved searches"
            )

        logger.info(f"Scheduled run complete: {total_new} new jobs, {total_with_company} with companies")

    async def _run_single_search(self, query_info: dict) -> tuple[int, int]:
        query_id = query_info["id"]
        query_name = query_info["name"]

        try:
            request = SearchRequest(
                keywords=query_info["keywords"],
                search_type=query_info["search_type"] or "AND",
                max_pages=min(query_info["max_pages"], self._max_pages_per_search)
            )

            scraped_jobs = await nodriver_scraper.search_jobs(request)

            new_count = 0
            company_count = 0

            # Use a fresh session for storing jobs
            async with async_session_maker() as db:
                for job_data in scraped_jobs:
                    has_mention, company_name, confidence, context = company_detector.has_company_mention(
                        job_data.description
                    )

                    # Only store jobs with company mentions
                    if not has_mention:
                        continue

                    existing = await db.execute(
                        select(Job).where(Job.upwork_id == job_data.upwork_id)
                    )
                    if existing.scalar_one_or_none():
                        continue

                    job = Job(
                        **job_data.model_dump(),
                        has_company_mention=True,
                        detected_company_name=company_name,
                        company_confidence=confidence,
                        company_context=context
                    )
                    db.add(job)
                    new_count += 1
                    company_count += 1

                # Update query stats
                query_result = await db.execute(select(SearchQuery).where(SearchQuery.id == query_id))
                query = query_result.scalar_one_or_none()
                if query:
                    query.run_count = (query.run_count or 0) + 1
                    query.last_run_at = datetime.now()
                    query.last_new_jobs = new_count

                # Create run record
                run = SchedulerRun(
                    search_query_id=query_id,
                    status="completed",
                    jobs_found=len(scraped_jobs),
                    new_jobs=new_count,
                    jobs_with_company=company_count,
                    completed_at=datetime.now()
                )
                db.add(run)
                await db.commit()

            logger.info(f"Search '{query_name}': {len(scraped_jobs)} found, {new_count} new with company")
            return new_count, company_count

        except Exception as e:
            # Log the failure
            async with async_session_maker() as db:
                run = SchedulerRun(
                    search_query_id=query_id,
                    status="failed",
                    error_message=str(e),
                    completed_at=datetime.now()
                )
                db.add(run)
                await db.commit()
            raise

    async def run_now(self):
        """Trigger an immediate run."""
        if self._current_run_id:
            return {"error": "A run is already in progress"}

        asyncio.create_task(self._run_scheduled_searches())
        return {"message": "Scheduled run triggered"}

    async def get_run_history(self, limit: int = 20) -> list:
        async with async_session_maker() as db:
            result = await db.execute(
                select(SchedulerRun)
                .order_by(SchedulerRun.started_at.desc())
                .limit(limit)
            )
            runs = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "search_query_id": r.search_query_id,
                    "status": r.status,
                    "jobs_found": r.jobs_found,
                    "new_jobs": r.new_jobs,
                    "jobs_with_company": r.jobs_with_company,
                    "error_message": r.error_message,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None
                }
                for r in runs
            ]


scheduler_service = SchedulerService()
