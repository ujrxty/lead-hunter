from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    upwork_id = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    url = Column(String(1000), nullable=False)

    # Client info
    client_country = Column(String(100))
    client_rating = Column(Float)
    client_total_spent = Column(String(50))
    client_hires = Column(Integer)

    # Job details
    budget_type = Column(String(20))  # fixed or hourly
    budget_min = Column(Float)
    budget_max = Column(Float)
    experience_level = Column(String(50))
    duration = Column(String(100))
    job_type = Column(String(50))

    # Company detection
    has_company_mention = Column(Boolean, default=False, index=True)
    detected_company_name = Column(String(500))
    company_confidence = Column(Float, default=0.0)
    company_context = Column(Text)

    # Search metadata
    search_keywords = Column(JSON)

    # Timestamps
    posted_at = Column(DateTime)
    scraped_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # User actions
    is_bookmarked = Column(Boolean, default=False)
    is_hidden = Column(Boolean, default=False)
    notes = Column(Text)


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True, index=True)
    keywords = Column(JSON, nullable=False)
    search_type = Column(String(20), default="AND")  # AND or OR
    filters = Column(JSON)

    is_active = Column(Boolean, default=True)
    run_count = Column(Integer, default=0)
    last_run_at = Column(DateTime)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200))
    service_description = Column(Text)
    skills = Column(JSON)
    generated_keywords = Column(JSON)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EnrichedLead(Base):
    __tablename__ = "enriched_leads"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, index=True)
    company_name = Column(String(500), index=True)

    # Contact info
    website = Column(String(1000))
    emails = Column(JSON)
    phones = Column(JSON)

    # Social profiles
    linkedin = Column(String(500))
    twitter = Column(String(500))
    instagram = Column(String(500))
    facebook = Column(String(500))

    # Additional info
    address = Column(Text)
    description = Column(Text)

    # AI analysis
    lead_score = Column(Integer, default=0)
    ai_analysis = Column(JSON)

    # WhatsApp verification
    whatsapp_verified = Column(JSON)

    # Status
    status = Column(String(50), default="pending")  # pending, enriched, contacted
    enriched_at = Column(DateTime)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AppSetting(Base):
    """Runtime-editable settings (API keys, model choice, scrape defaults).

    Env vars still win at boot for a fresh install, but anything set via the
    /api/settings endpoint overrides them for the running process. This lets
    the user configure keys from the UI instead of editing .env.
    """
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
