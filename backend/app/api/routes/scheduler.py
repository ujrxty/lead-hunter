from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from pydantic import BaseModel
from typing import Optional, List
import asyncio

from app.core.database import get_db
from app.models.job import SearchQuery
from app.api.services.scheduler_service import scheduler_service
from app.api.services.notification_service import notification_service

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class SchedulerConfig(BaseModel):
    interval_minutes: int = 30


class SavedSearchCreate(BaseModel):
    name: str
    keywords: List[str]
    search_type: str = "AND"
    max_pages: int = 5
    is_scheduled: bool = True


class SavedSearchUpdate(BaseModel):
    name: Optional[str] = None
    keywords: Optional[List[str]] = None
    search_type: Optional[str] = None
    max_pages: Optional[int] = None
    is_scheduled: Optional[bool] = None
    is_active: Optional[bool] = None


@router.get("/status")
async def get_status():
    """Get scheduler status."""
    return scheduler_service.status


@router.post("/start")
async def start_scheduler(config: SchedulerConfig = None):
    """Start the scheduler."""
    interval = config.interval_minutes if config else 30
    await scheduler_service.start(interval)
    return scheduler_service.status


@router.post("/stop")
async def stop_scheduler():
    """Stop the scheduler."""
    await scheduler_service.stop()
    return scheduler_service.status


@router.post("/run-now")
async def run_now():
    """Trigger an immediate run."""
    return await scheduler_service.run_now()


@router.put("/interval")
async def set_interval(config: SchedulerConfig):
    """Update scheduler interval."""
    await scheduler_service.set_interval(config.interval_minutes)
    return scheduler_service.status


@router.get("/history")
async def get_run_history(limit: int = Query(20, ge=1, le=100)):
    """Get scheduler run history."""
    return await scheduler_service.get_run_history(limit)


# Saved searches CRUD
@router.get("/searches")
async def get_saved_searches(db: AsyncSession = Depends(get_db)):
    """Get all saved searches."""
    result = await db.execute(
        select(SearchQuery).order_by(SearchQuery.created_at.desc())
    )
    queries = result.scalars().all()
    return [
        {
            "id": q.id,
            "name": q.name,
            "keywords": q.keywords,
            "search_type": q.search_type,
            "max_pages": q.max_pages,
            "is_active": q.is_active,
            "is_scheduled": q.is_scheduled,
            "run_count": q.run_count,
            "last_run_at": q.last_run_at.isoformat() if q.last_run_at else None,
            "last_new_jobs": q.last_new_jobs,
            "created_at": q.created_at.isoformat() if q.created_at else None
        }
        for q in queries
    ]


@router.post("/searches")
async def create_saved_search(
    search: SavedSearchCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new saved search."""
    query = SearchQuery(
        name=search.name,
        keywords=search.keywords,
        search_type=search.search_type,
        max_pages=search.max_pages,
        is_scheduled=search.is_scheduled,
        is_active=True
    )
    db.add(query)
    await db.commit()
    await db.refresh(query)

    return {
        "id": query.id,
        "name": query.name,
        "keywords": query.keywords,
        "is_scheduled": query.is_scheduled
    }


@router.put("/searches/{search_id}")
async def update_saved_search(
    search_id: int,
    update_data: SavedSearchUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a saved search."""
    result = await db.execute(select(SearchQuery).where(SearchQuery.id == search_id))
    query = result.scalar_one_or_none()

    if not query:
        raise HTTPException(status_code=404, detail="Search not found")

    for key, value in update_data.model_dump(exclude_unset=True).items():
        setattr(query, key, value)

    await db.commit()
    return {"message": "Search updated"}


@router.delete("/searches/{search_id}")
async def delete_saved_search(
    search_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a saved search."""
    result = await db.execute(
        delete(SearchQuery).where(SearchQuery.id == search_id)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Search not found")
    await db.commit()
    return {"message": "Search deleted"}


# SSE notifications endpoint
@router.get("/notifications/stream")
async def notification_stream():
    """SSE stream for real-time notifications."""
    queue = await notification_service.subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            notification_service.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/notifications/recent")
async def get_recent_notifications(limit: int = Query(20, ge=1, le=50)):
    """Get recent notifications."""
    return notification_service.get_recent_notifications(limit)
