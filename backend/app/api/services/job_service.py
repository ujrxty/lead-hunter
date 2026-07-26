from typing import List, Optional
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.job import Job, SearchQuery
from app.schemas.job import JobCreate, JobUpdate, SearchRequest
from app.api.detectors.company_detector import company_detector
from app.api.scrapers.nodriver_scraper import nodriver_scraper


class JobService:
    """Service for managing jobs."""

    async def create_or_update_job(self, db: AsyncSession, job_data: JobCreate) -> Job:
        """Create a new job or update if exists."""
        result = await db.execute(
            select(Job).where(Job.upwork_id == job_data.upwork_id)
        )
        existing_job = result.scalar_one_or_none()

        has_mention, company_name, confidence, context = company_detector.has_company_mention(
            job_data.description
        )

        if existing_job:
            for key, value in job_data.model_dump(exclude_unset=True).items():
                setattr(existing_job, key, value)
            existing_job.has_company_mention = has_mention
            existing_job.detected_company_name = company_name
            existing_job.company_confidence = confidence
            existing_job.company_context = context
            await db.flush()
            return existing_job

        job = Job(
            **job_data.model_dump(),
            has_company_mention=has_mention,
            detected_company_name=company_name,
            company_confidence=confidence,
            company_context=context
        )
        db.add(job)
        await db.flush()
        return job

    async def get_jobs(
        self,
        db: AsyncSession,
        page: int = 1,
        per_page: int = 20,
        only_company_mentions: bool = False,
        search_term: Optional[str] = None,
        is_bookmarked: Optional[bool] = None,
        min_confidence: float = 0.0
    ) -> tuple[List[Job], int, int]:
        """Get jobs with filters."""
        query = select(Job).where(Job.is_hidden == False)

        if only_company_mentions:
            query = query.where(Job.has_company_mention == True)
            if min_confidence > 0:
                query = query.where(Job.company_confidence >= min_confidence)

        if search_term:
            search = f"%{search_term}%"
            query = query.where(
                or_(
                    Job.title.ilike(search),
                    Job.description.ilike(search),
                    Job.detected_company_name.ilike(search)
                )
            )

        if is_bookmarked is not None:
            query = query.where(Job.is_bookmarked == is_bookmarked)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        company_count_query = select(func.count()).where(
            and_(Job.has_company_mention == True, Job.is_hidden == False)
        )
        company_count_result = await db.execute(company_count_query)
        company_count = company_count_result.scalar()

        query = query.order_by(Job.has_company_mention.desc(), Job.company_confidence.desc(), Job.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await db.execute(query)
        jobs = result.scalars().all()

        return list(jobs), total, company_count

    async def get_job_by_id(self, db: AsyncSession, job_id: int) -> Optional[Job]:
        """Get a job by ID."""
        result = await db.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def update_job(self, db: AsyncSession, job_id: int, update_data: JobUpdate) -> Optional[Job]:
        """Update a job."""
        job = await self.get_job_by_id(db, job_id)
        if not job:
            return None

        for key, value in update_data.model_dump(exclude_unset=True).items():
            setattr(job, key, value)

        await db.flush()
        return job

    async def search_and_store_jobs(self, db: AsyncSession, request: SearchRequest) -> List[Job]:
        """Search Upwork and store jobs."""
        logger.info(f"Starting search with keywords: {request.keywords}")

        scraped_jobs = await nodriver_scraper.search_jobs(request)
        logger.info(f"Scraped {len(scraped_jobs)} jobs")

        stored_jobs = []
        for job_data in scraped_jobs:
            job = await self.create_or_update_job(db, job_data)
            stored_jobs.append(job)

        await db.commit()
        logger.info(f"Stored {len(stored_jobs)} jobs")

        return stored_jobs

    async def save_search_query(self, db: AsyncSession, request: SearchRequest) -> SearchQuery:
        """Save a search query."""
        search_query = SearchQuery(
            keywords=request.keywords,
            search_type=request.search_type,
            filters={
                "category": request.category,
                "experience_level": request.experience_level,
                "budget_min": request.budget_min,
                "budget_max": request.budget_max
            }
        )
        db.add(search_query)
        await db.flush()
        return search_query

    async def get_search_queries(self, db: AsyncSession) -> List[SearchQuery]:
        """Get all search queries."""
        result = await db.execute(
            select(SearchQuery).order_by(SearchQuery.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_stats(self, db: AsyncSession) -> dict:
        """Get job statistics."""
        total = await db.execute(
            select(func.count(Job.id)).where(Job.is_hidden == False)
        )
        with_company = await db.execute(
            select(func.count(Job.id)).where(
                and_(Job.has_company_mention == True, Job.is_hidden == False)
            )
        )
        bookmarked = await db.execute(
            select(func.count(Job.id)).where(
                and_(Job.is_bookmarked == True, Job.is_hidden == False)
            )
        )

        return {
            "total_jobs": total.scalar() or 0,
            "jobs_with_company": with_company.scalar() or 0,
            "bookmarked_jobs": bookmarked.scalar() or 0
        }


job_service = JobService()
