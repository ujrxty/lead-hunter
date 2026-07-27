import asyncio
import json
from typing import Dict, Set, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from loguru import logger


@dataclass
class Notification:
    type: str  # "new_jobs", "scheduler_status", "error"
    title: str
    message: str
    data: Dict[str, Any] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.data is None:
            self.data = {}


class NotificationService:
    """SSE-based notification service for real-time updates."""

    def __init__(self):
        self._subscribers: Set[asyncio.Queue] = set()
        self._history: list[Notification] = []
        self._max_history = 50

    async def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self._subscribers.add(queue)
        logger.info(f"New SSE subscriber, total: {len(self._subscribers)}")
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        self._subscribers.discard(queue)
        logger.info(f"SSE subscriber left, total: {len(self._subscribers)}")

    async def broadcast(self, notification: Notification):
        self._history.append(notification)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        data = json.dumps(asdict(notification))
        dead_queues = set()

        for queue in self._subscribers:
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                dead_queues.add(queue)

        for q in dead_queues:
            self._subscribers.discard(q)

    async def notify_new_jobs(self, new_count: int, with_company: int, search_name: str = None):
        if new_count == 0:
            return

        title = "New Jobs Found!" if with_company > 0 else "New Jobs Scraped"
        message = f"{new_count} new jobs"
        if with_company > 0:
            message += f" ({with_company} hot leads)"
        if search_name:
            message += f" from '{search_name}'"

        await self.broadcast(Notification(
            type="new_jobs",
            title=title,
            message=message,
            data={
                "new_count": new_count,
                "with_company": with_company,
                "search_name": search_name
            }
        ))

    async def notify_scheduler_status(self, status: str, message: str = None, next_run: str = None):
        await self.broadcast(Notification(
            type="scheduler_status",
            title=f"Scheduler {status.title()}",
            message=message or f"Scheduler is now {status}",
            data={"status": status, "next_run": next_run}
        ))

    async def notify_error(self, error: str, context: str = None):
        await self.broadcast(Notification(
            type="error",
            title="Error",
            message=error,
            data={"context": context}
        ))

    def get_recent_notifications(self, limit: int = 20) -> list:
        return [asdict(n) for n in self._history[-limit:]]


notification_service = NotificationService()
