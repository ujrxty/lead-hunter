from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class JobBase(BaseModel):
    upwork_id: str
    title: str
    description: str
    url: str


class JobCreate(JobBase):
    client_country: Optional[str] = None
    client_rating: Optional[float] = None
    client_total_spent: Optional[str] = None
    client_hires: Optional[int] = None
    budget_type: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    experience_level: Optional[str] = None
    duration: Optional[str] = None
    job_type: Optional[str] = None
    posted_at: Optional[datetime] = None
    search_keywords: Optional[List[str]] = None


class JobResponse(JobBase):
    id: int
    client_country: Optional[str]
    client_rating: Optional[float]
    client_total_spent: Optional[str]
    client_hires: Optional[int]
    budget_type: Optional[str]
    budget_min: Optional[float]
    budget_max: Optional[float]
    experience_level: Optional[str]
    duration: Optional[str]
    job_type: Optional[str]
    has_company_mention: bool
    detected_company_name: Optional[str]
    company_confidence: float
    company_context: Optional[str]
    search_keywords: Optional[List[str]]
    posted_at: Optional[datetime]
    scraped_at: Optional[datetime]
    is_bookmarked: bool
    is_hidden: bool
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    per_page: int
    has_company_mention_count: int


class JobUpdate(BaseModel):
    is_bookmarked: Optional[bool] = None
    is_hidden: Optional[bool] = None
    notes: Optional[str] = None


class SearchQueryCreate(BaseModel):
    keywords: List[str] = Field(..., min_length=1)
    search_type: str = Field(default="AND", pattern="^(AND|OR)$")
    filters: Optional[dict] = None


class SearchQueryResponse(BaseModel):
    id: int
    keywords: List[str]
    search_type: str
    filters: Optional[dict]
    is_active: bool
    run_count: int
    last_run_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    keywords: List[str] = Field(..., min_length=1, max_length=10)
    search_type: str = Field(default="AND", pattern="^(AND|OR)$")
    category: Optional[str] = None
    experience_level: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    client_hires_min: Optional[int] = None
    only_company_mentions: bool = False
    # 0 means "scrape until Upwork stops paginating" (bounded by hard_max_pages
    # inside the scraper). 1-N caps at that many pages of ~10 results each.
    max_pages: int = Field(default=10, ge=0, le=100)
