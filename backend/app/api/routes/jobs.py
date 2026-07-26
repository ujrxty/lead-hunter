from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.job import (
    JobResponse,
    JobListResponse,
    JobUpdate,
    SearchRequest,
    SearchQueryResponse
)
from app.api.services.job_service import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
async def get_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    only_company_mentions: bool = Query(False),
    search: Optional[str] = Query(None),
    bookmarked: Optional[bool] = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db)
):
    """Get all jobs with optional filters."""
    jobs, total, company_count = await job_service.get_jobs(
        db,
        page=page,
        per_page=per_page,
        only_company_mentions=only_company_mentions,
        search_term=search,
        is_bookmarked=bookmarked,
        min_confidence=min_confidence
    )

    return JobListResponse(
        jobs=[JobResponse.model_validate(job) for job in jobs],
        total=total,
        page=page,
        per_page=per_page,
        has_company_mention_count=company_count
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific job."""
    job = await job_service.get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.model_validate(job)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: int,
    update_data: JobUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a job (bookmark, hide, notes)."""
    job = await job_service.update_job(db, job_id, update_data)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.model_validate(job)


@router.post("/search")
async def search_jobs(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Search for jobs on Upwork."""
    await job_service.save_search_query(db, request)
    await db.commit()

    jobs = await job_service.search_and_store_jobs(db, request)

    jobs_with_company = [j for j in jobs if j.has_company_mention]

    return {
        "message": f"Found {len(jobs)} jobs, {len(jobs_with_company)} with company mentions",
        "total_found": len(jobs),
        "with_company_mention": len(jobs_with_company),
        "keywords": request.keywords
    }


@router.get("/queries/history", response_model=list[SearchQueryResponse])
async def get_search_history(db: AsyncSession = Depends(get_db)):
    """Get search query history."""
    queries = await job_service.get_search_queries(db)
    return [SearchQueryResponse.model_validate(q) for q in queries]


@router.get("/stats/overview")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get job statistics."""
    return await job_service.get_stats(db)


@router.get("/session/status")
async def session_status():
    """Check if scraper can connect to Upwork (nodriver bypasses Cloudflare automatically)."""
    return {"status": "ready", "message": "Using nodriver - no session needed, Cloudflare bypassed automatically"}
