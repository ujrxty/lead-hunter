"""AI and Lead Enrichment Routes."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from loguru import logger

from app.core.database import get_db
from app.models.job import Job, UserProfile, EnrichedLead
from app.api.services.ai_service import ai_service
from app.api.services.enrichment_service import enrichment_service

router = APIRouter(prefix="/ai", tags=["ai"])


class ProfileRequest(BaseModel):
    name: Optional[str] = None
    service_description: str
    skills: Optional[List[str]] = None


class ProfileResponse(BaseModel):
    id: int
    name: Optional[str]
    service_description: str
    skills: Optional[List[str]]
    generated_keywords: Optional[List[str]]


class KeywordsResponse(BaseModel):
    keywords: List[str]


class EnrichRequest(BaseModel):
    job_id: int


class OutreachRequest(BaseModel):
    job_id: int
    user_profile: Optional[str] = None


@router.post("/profile", response_model=ProfileResponse)
async def create_or_update_profile(
    request: ProfileRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create or update user profile and generate keywords."""
    # Generate keywords using AI
    keywords = await ai_service.generate_keywords(request.service_description)

    # Check for existing profile
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()

    if profile:
        profile.name = request.name
        profile.service_description = request.service_description
        profile.skills = request.skills
        profile.generated_keywords = keywords
    else:
        profile = UserProfile(
            name=request.name,
            service_description=request.service_description,
            skills=request.skills,
            generated_keywords=keywords
        )
        db.add(profile)

    await db.commit()
    await db.refresh(profile)

    return ProfileResponse(
        id=profile.id,
        name=profile.name,
        service_description=profile.service_description,
        skills=profile.skills,
        generated_keywords=profile.generated_keywords
    )


@router.get("/profile", response_model=Optional[ProfileResponse])
async def get_profile(db: AsyncSession = Depends(get_db)):
    """Get current user profile."""
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()

    if not profile:
        return None

    return ProfileResponse(
        id=profile.id,
        name=profile.name,
        service_description=profile.service_description,
        skills=profile.skills,
        generated_keywords=profile.generated_keywords
    )


@router.post("/keywords", response_model=KeywordsResponse)
async def generate_keywords(request: ProfileRequest):
    """Generate search keywords from service description."""
    keywords = await ai_service.generate_keywords(request.service_description)
    return KeywordsResponse(keywords=keywords)


@router.get("/status")
async def ai_status():
    """Report whether AI (Groq) is configured, so the UI can adapt."""
    return {
        "configured": ai_service.is_configured,
        "model": ai_service.model,
        "provider": "groq",
    }


@router.post("/enrich/{job_id}")
async def enrich_lead(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Enrich a job lead with company contact information."""
    # Get job
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.detected_company_name:
        raise HTTPException(status_code=400, detail="Job has no detected company name")

    # Check if already enriched
    existing = await db.execute(
        select(EnrichedLead).where(EnrichedLead.job_id == job_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Lead already enriched")

    # Create pending enriched lead
    lead = EnrichedLead(
        job_id=job_id,
        company_name=job.detected_company_name,
        status="pending"
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    # Run enrichment in background
    background_tasks.add_task(
        run_enrichment,
        lead.id,
        job.detected_company_name
    )

    return {"message": "Enrichment started", "lead_id": lead.id}


async def run_enrichment(lead_id: int, company_name: str):
    """Background task to enrich a lead."""
    from app.core.database import async_session_maker
    from datetime import datetime

    logger.info(f"Starting enrichment for lead {lead_id}: {company_name}")

    try:
        # Get enrichment data
        data = await enrichment_service.enrich_company(company_name)

        # Update database
        async with async_session_maker() as db:
            result = await db.execute(
                select(EnrichedLead).where(EnrichedLead.id == lead_id)
            )
            lead = result.scalar_one_or_none()

            if lead:
                lead.website = data.get("website")
                lead.emails = data.get("emails", [])
                lead.phones = data.get("phones", [])
                lead.linkedin = data.get("linkedin")
                lead.twitter = data.get("twitter")
                lead.instagram = data.get("instagram")
                lead.facebook = data.get("facebook")
                lead.address = data.get("address")
                lead.description = data.get("description")
                lead.status = "enriched"
                lead.enriched_at = datetime.now()

                await db.commit()
                logger.info(f"Enrichment complete for lead {lead_id}")

    except Exception as e:
        logger.error(f"Enrichment failed for lead {lead_id}: {e}")

        async with async_session_maker() as db:
            result = await db.execute(
                select(EnrichedLead).where(EnrichedLead.id == lead_id)
            )
            lead = result.scalar_one_or_none()
            if lead:
                lead.status = "failed"
                await db.commit()


@router.get("/leads")
async def get_enriched_leads(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all enriched leads."""
    query = select(EnrichedLead).order_by(EnrichedLead.created_at.desc())

    if status:
        query = query.where(EnrichedLead.status == status)

    result = await db.execute(query)
    leads = result.scalars().all()

    return [
        {
            "id": lead.id,
            "job_id": lead.job_id,
            "company_name": lead.company_name,
            "website": lead.website,
            "emails": lead.emails,
            "phones": lead.phones,
            "linkedin": lead.linkedin,
            "twitter": lead.twitter,
            "instagram": lead.instagram,
            "facebook": lead.facebook,
            "status": lead.status,
            "enriched_at": lead.enriched_at
        }
        for lead in leads
    ]


@router.get("/recommendations")
async def get_recommendations(db: AsyncSession = Depends(get_db)):
    """Get AI-recommended jobs (Hot Leads, Best Match, Fresh)."""
    from datetime import datetime, timedelta

    # Get jobs with company mentions
    result = await db.execute(
        select(Job)
        .where(Job.has_company_mention == True)
        .where(Job.is_hidden == False)
        .order_by(Job.created_at.desc())
        .limit(50)
    )
    jobs = result.scalars().all()

    hot_leads = []
    fresh_jobs = []
    one_hour_ago = datetime.now() - timedelta(hours=1)

    for job in jobs:
        job_dict = {
            "id": job.id,
            "title": job.title,
            "detected_company_name": job.detected_company_name,
            "company_confidence": job.company_confidence,
            "client_rating": job.client_rating,
            "client_total_spent": job.client_total_spent,
            "budget_type": job.budget_type,
            "budget_min": job.budget_min,
            "budget_max": job.budget_max,
            "posted_at": job.posted_at.isoformat() if job.posted_at else None,
            "url": job.url
        }

        # Calculate a quick score
        score = 40  # Base score for jobs with company mention

        # Company confidence boost (major factor)
        if job.company_confidence > 0.9:
            score += 25
        elif job.company_confidence > 0.8:
            score += 20
        elif job.company_confidence > 0.7:
            score += 15

        # Client rating boost
        if job.client_rating:
            if job.client_rating >= 4.8:
                score += 15
            elif job.client_rating >= 4.5:
                score += 10
            elif job.client_rating >= 4.0:
                score += 5

        # Client spending boost
        if job.client_total_spent:
            spent_str = job.client_total_spent.lower()
            if 'k' in spent_str or '000' in spent_str:
                score += 10
            if 'm' in spent_str:
                score += 20

        # Budget boost
        if job.budget_min and job.budget_min > 50:
            score += 10

        job_dict["score"] = min(score, 100)
        job_dict["recommendation"] = "apply" if score >= 60 else "maybe" if score >= 45 else "skip"

        # Categorize - lower threshold for now until we have more data
        if score >= 55:
            hot_leads.append(job_dict)

        if job.posted_at and job.posted_at > one_hour_ago:
            fresh_jobs.append(job_dict)

    # Sort by score
    hot_leads.sort(key=lambda x: x["score"], reverse=True)

    return {
        "hot_leads": hot_leads[:10],
        "fresh_opportunities": fresh_jobs[:10],
        "total_with_company": len(jobs)
    }


@router.get("/leads/{lead_id}")
async def get_enriched_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific enriched lead."""
    result = await db.execute(
        select(EnrichedLead).where(EnrichedLead.id == lead_id)
    )
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return {
        "id": lead.id,
        "job_id": lead.job_id,
        "company_name": lead.company_name,
        "website": lead.website,
        "emails": lead.emails,
        "phones": lead.phones,
        "linkedin": lead.linkedin,
        "twitter": lead.twitter,
        "instagram": lead.instagram,
        "facebook": lead.facebook,
        "address": lead.address,
        "description": lead.description,
        "lead_score": lead.lead_score,
        "ai_analysis": lead.ai_analysis,
        "whatsapp_verified": lead.whatsapp_verified,
        "status": lead.status,
        "enriched_at": lead.enriched_at
    }


@router.post("/outreach/{job_id}")
async def generate_outreach(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Generate AI outreach message for a job."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get user profile
    profile_result = await db.execute(select(UserProfile).limit(1))
    profile = profile_result.scalar_one_or_none()

    user_profile = profile.service_description if profile else "Experienced freelancer"

    message = await ai_service.generate_outreach(
        {
            "title": job.title,
            "description": job.description,
            "detected_company_name": job.detected_company_name
        },
        user_profile
    )

    return {"outreach_message": message}


@router.post("/analyze/{job_id}")
async def analyze_lead(job_id: int, db: AsyncSession = Depends(get_db)):
    """Analyze a job lead quality using AI."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    analysis = await ai_service.analyze_lead_quality({
        "title": job.title,
        "description": job.description,
        "budget_type": job.budget_type,
        "budget_min": job.budget_min,
        "budget_max": job.budget_max,
        "client_rating": job.client_rating,
        "client_hires": job.client_hires,
        "detected_company_name": job.detected_company_name,
        "company_confidence": job.company_confidence
    })

    return analysis


class ProposalRequest(BaseModel):
    tone: str = "professional"  # professional, friendly, enthusiastic


class ProposalResponse(BaseModel):
    cover_letter: str
    why_fit: str
    approach: str
    timeline: str
    questions: List[str]
    full_proposal: str


@router.post("/proposal/{job_id}", response_model=ProposalResponse)
async def generate_proposal(
    job_id: int,
    request: ProposalRequest = ProposalRequest(),
    db: AsyncSession = Depends(get_db)
):
    """Generate a full proposal/cover letter for a job."""
    # Get job
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get user profile
    profile_result = await db.execute(select(UserProfile).limit(1))
    profile = profile_result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Please create a profile first to generate proposals"
        )

    # Generate proposal
    proposal = await ai_service.generate_full_proposal(
        job={
            "title": job.title,
            "description": job.description,
            "detected_company_name": job.detected_company_name,
            "budget_type": job.budget_type,
            "budget_min": job.budget_min,
            "budget_max": job.budget_max,
            "experience_level": job.experience_level,
            "duration": job.duration
        },
        user_profile={
            "name": profile.name,
            "service_description": profile.service_description,
            "skills": profile.skills or []
        },
        tone=request.tone
    )

    return ProposalResponse(**proposal)


@router.post("/quick-response/{job_id}")
async def generate_quick_response(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Generate a quick 2-3 sentence response for fast applications."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    profile_result = await db.execute(select(UserProfile).limit(1))
    profile = profile_result.scalar_one_or_none()

    response = await ai_service.generate_quick_response(
        job={
            "title": job.title,
            "description": job.description
        },
        user_profile={
            "name": profile.name if profile else "Freelancer",
            "skills": profile.skills if profile else []
        }
    )

    return {"quick_response": response}
