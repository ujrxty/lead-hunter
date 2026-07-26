"""AI Service using Groq for intelligent features.

Key + model are read from the runtime settings service on every call, so
edits from the UI (/api/settings) take effect immediately without a restart.
"""
import json
import re
import asyncio
from typing import List, Optional, Dict
from groq import Groq
from loguru import logger


class AIService:
    def __init__(self):
        self._client = None
        self._client_key = None
        self._model_cache = "llama-3.3-70b-versatile"

    async def _resolve(self):
        """Return (client, model) using latest DB-backed settings.
        Rebuilds client if the key changed (user updated it in the UI)."""
        from app.api.services.settings_service import settings_service
        key = await settings_service.get("groq_api_key")
        model = await settings_service.get("groq_model") or "llama-3.3-70b-versatile"
        self._model_cache = model
        if not key:
            return None, model
        if self._client is None or self._client_key != key:
            self._client = Groq(api_key=key)
            self._client_key = key
        return self._client, model

    # Legacy sync accessors — kept so existing sync sites still compile.
    # New code should call `client, model = await self._resolve()`.
    def _get_client(self):
        return self._client  # may be None until _resolve() has run once

    @property
    def model(self) -> str:
        return self._model_cache

    @property
    def is_configured(self) -> bool:
        from app.api.services.settings_service import settings_service
        return bool(settings_service._cache.get("groq_api_key"))

    async def generate_keywords(self, user_description: str) -> List[str]:
        """Generate Upwork search keywords from user's service description."""
        client, _model = await self._resolve()
        if not client:
            logger.warning("No Groq API key, using fallback keywords")
            return self._fallback_keywords(user_description)

        try:
            response = client.chat.completions.create(
                model=_model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at finding freelance jobs on Upwork.
Given a description of services someone offers, generate 10-15 highly relevant Upwork search keywords.
Focus on keywords that clients actually use when posting jobs.
Return ONLY a JSON array of strings, nothing else."""
                    },
                    {
                        "role": "user",
                        "content": f"I offer these services: {user_description}\n\nGenerate Upwork search keywords:"
                    }
                ],
                temperature=0.7,
                max_tokens=500
            )
            content = response.choices[0].message.content.strip()
            # Parse JSON array
            keywords = json.loads(content)
            return keywords if isinstance(keywords, list) else []
        except Exception as e:
            logger.error(f"AI keyword generation failed: {e}")
            return self._fallback_keywords(user_description)

    def _fallback_keywords(self, description: str) -> List[str]:
        """Extract basic keywords from description."""
        words = re.findall(r'\b[a-zA-Z]{4,}\b', description.lower())
        common = {'that', 'this', 'with', 'from', 'have', 'been', 'will', 'would', 'could', 'should'}
        return list(set(w for w in words if w not in common))[:10]

    async def extract_company_info(self, job_description: str) -> Dict:
        """Extract company information from job description using AI."""
        client, _model = await self._resolve()
        if not client:
            return {"company_name": None, "confidence": 0, "context": None}

        try:
            response = client.chat.completions.create(
                model=_model,
                messages=[
                    {
                        "role": "system",
                        "content": """Analyze the job description and extract any company information.
Look for:
- Explicit company names mentioned
- Brand names
- Product names that indicate a company
- Hints about company identity

Return JSON with:
{
    "company_name": "name or null",
    "confidence": 0.0-1.0,
    "context": "the sentence mentioning the company",
    "company_type": "startup/agency/enterprise/unknown",
    "industry": "tech/finance/healthcare/etc"
}"""
                    },
                    {
                        "role": "user",
                        "content": job_description
                    }
                ],
                temperature=0.3,
                max_tokens=300
            )
            content = response.choices[0].message.content.strip()
            # Find JSON in response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"company_name": None, "confidence": 0, "context": None}
        except Exception as e:
            logger.error(f"AI company extraction failed: {e}")
            return {"company_name": None, "confidence": 0, "context": None}

    async def generate_outreach(self, job: Dict, user_profile: str) -> str:
        """Generate personalized outreach message for a job."""
        client, _model = await self._resolve()
        if not client:
            return ""

        try:
            response = client.chat.completions.create(
                model=_model,
                messages=[
                    {
                        "role": "system",
                        "content": """Write a short, personalized Upwork proposal intro (2-3 sentences).
Be specific about the job, mention the company if known, and show relevant experience.
Don't be generic. Be confident but not arrogant. No fluff."""
                    },
                    {
                        "role": "user",
                        "content": f"""Job Title: {job.get('title')}
Job Description: {job.get('description', '')[:500]}
Company: {job.get('detected_company_name', 'Unknown')}

My Profile: {user_profile}

Write a proposal intro:"""
                    }
                ],
                temperature=0.8,
                max_tokens=200
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"AI outreach generation failed: {e}")
            return ""

    async def analyze_lead_quality(self, job: Dict) -> Dict:
        """Score a lead based on various factors."""
        client, _model = await self._resolve()
        if not client:
            return {"score": 50, "reasons": []}

        try:
            response = client.chat.completions.create(
                model=_model,
                messages=[
                    {
                        "role": "system",
                        "content": """Analyze this Upwork job and score it as a lead (0-100).
Consider:
- Budget (higher = better)
- Client history (hires, spend)
- Job clarity (well-defined = better)
- Company mention (named company = better)
- Red flags (unrealistic expectations, very low budget)

Return JSON:
{
    "score": 0-100,
    "reasons": ["reason1", "reason2"],
    "recommendation": "apply/skip/maybe"
}"""
                    },
                    {
                        "role": "user",
                        "content": json.dumps(job, default=str)
                    }
                ],
                temperature=0.3,
                max_tokens=200
            )
            content = response.choices[0].message.content.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"score": 50, "reasons": [], "recommendation": "maybe"}
        except Exception as e:
            logger.error(f"AI lead analysis failed: {e}")
            return {"score": 50, "reasons": [], "recommendation": "maybe"}

    async def generate_full_proposal(
        self,
        job: Dict,
        user_profile: Dict,
        tone: str = "professional"
    ) -> Dict:
        """Generate a complete Upwork proposal with all sections.

        Args:
            job: Job details dict
            user_profile: User profile with name, service_description, skills
            tone: professional, friendly, or enthusiastic

        Returns:
            Dict with cover_letter, why_fit, approach, timeline, questions, full_proposal
        """
        client, _model = await self._resolve()
        if not client:
            return self._fallback_proposal(job, user_profile)

        tone_instructions = {
            "professional": "Write in a professional, confident tone. Be direct and businesslike.",
            "friendly": "Write in a warm, approachable tone. Be personable while staying professional.",
            "enthusiastic": "Write with energy and excitement about the project. Show genuine interest.",
        }

        try:
            response = client.chat.completions.create(
                model=_model,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an expert Upwork proposal writer with a 90%+ hire rate.
{tone_instructions.get(tone, tone_instructions['professional'])}

Generate a complete, highly personalized Upwork proposal that addresses the client's SPECIFIC needs.
The proposal must show you actually READ and understood the job posting.

Return a JSON object with these sections:
{{
    "cover_letter": "2-3 paragraph opening that hooks the client. Reference specific details from their job. Show you understand their problem. Never start with 'I am' or 'Dear client'.",
    "why_fit": "2-3 bullet points explaining why YOU are perfect for THIS job. Match your skills to their requirements specifically.",
    "approach": "Brief description of how you would approach this specific project. Show expertise without being condescending.",
    "timeline": "Realistic timeline estimate with milestones if applicable.",
    "questions": ["Smart question 1", "Smart question 2"] // 2-3 questions that show you're thinking ahead
}}

Rules:
- Be SPECIFIC to this job, not generic
- Reference the company name if mentioned
- Don't oversell or use superlatives like "best" or "expert"
- Show, don't tell (mention relevant experience, don't just say "I have experience")
- Keep it concise - clients skim proposals
- No placeholder text or [brackets]"""
                    },
                    {
                        "role": "user",
                        "content": f"""JOB DETAILS:
Title: {job.get('title', 'N/A')}
Description: {job.get('description', '')[:1500]}
Company: {job.get('detected_company_name', 'Not mentioned')}
Budget: {job.get('budget_type', 'Not specified')} - ${job.get('budget_min', 'N/A')} to ${job.get('budget_max', 'N/A')}
Experience Level: {job.get('experience_level', 'Not specified')}
Duration: {job.get('duration', 'Not specified')}

MY PROFILE:
Name: {user_profile.get('name', 'Freelancer')}
Services: {user_profile.get('service_description', '')}
Skills: {', '.join(user_profile.get('skills', []))}

Generate the proposal sections:"""
                    }
                ],
                temperature=0.7,
                max_tokens=1500
            )
            content = response.choices[0].message.content.strip()

            # Parse JSON from response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
                result = self._normalize_proposal(result)

                # Combine into full proposal
                full_proposal = self._format_full_proposal(result)
                result['full_proposal'] = full_proposal

                return result

            return self._fallback_proposal(job, user_profile)

        except Exception as e:
            logger.error(f"AI proposal generation failed: {e}")
            return self._fallback_proposal(job, user_profile)

    @staticmethod
    def _as_text(value) -> str:
        """Coerce a section value (which the model may return as a list) to a string."""
        if isinstance(value, list):
            return "\n".join(
                f"- {v}" if not str(v).lstrip().startswith(("-", "•")) else str(v)
                for v in value
            )
        if value is None:
            return ""
        return str(value)

    def _normalize_proposal(self, result: Dict) -> Dict:
        """Ensure every proposal section matches the response schema.

        The LLM often returns bullet sections (why_fit, approach) as JSON
        arrays. ProposalResponse expects strings, and _format_full_proposal
        joins them, so coerce lists to text here and keep questions a list.
        """
        for key in ("cover_letter", "why_fit", "approach", "timeline"):
            result[key] = self._as_text(result.get(key))

        questions = result.get("questions")
        if isinstance(questions, str):
            questions = [q.strip("-• ").strip() for q in questions.splitlines() if q.strip()]
        elif isinstance(questions, list):
            questions = [str(q) for q in questions]
        else:
            questions = []
        result["questions"] = questions
        return result

    def _format_full_proposal(self, sections: Dict) -> str:
        """Format all sections into a complete proposal."""
        parts = []

        if sections.get('cover_letter'):
            parts.append(sections['cover_letter'])

        if sections.get('why_fit'):
            parts.append("\n**Why I'm the Right Fit:**")
            parts.append(sections['why_fit'])

        if sections.get('approach'):
            parts.append("\n**My Approach:**")
            parts.append(sections['approach'])

        if sections.get('timeline'):
            parts.append("\n**Timeline:**")
            parts.append(sections['timeline'])

        if sections.get('questions'):
            parts.append("\n**A Few Questions:**")
            for q in sections['questions']:
                parts.append(f"- {q}")

        parts.append("\nLooking forward to discussing this further!")

        return "\n".join(parts)

    def _fallback_proposal(self, job: Dict, user_profile: Dict) -> Dict:
        """Generate a basic proposal without AI."""
        name = user_profile.get('name', 'Hi')
        title = job.get('title', 'your project')

        return {
            "cover_letter": f"I'm interested in {title}. Based on your requirements, I believe I can deliver quality results efficiently.",
            "why_fit": "- Relevant experience in this area\n- Quick turnaround and communication\n- Focus on quality deliverables",
            "approach": "I would start by understanding your specific needs, then create a clear plan with milestones.",
            "timeline": "I can provide a detailed timeline after understanding the full scope.",
            "questions": [
                "What's your preferred timeline for this project?",
                "Are there any specific tools or technologies you'd like me to use?"
            ],
            "full_proposal": f"I'm interested in {title}. Based on your requirements, I believe I can deliver quality results efficiently.\n\nLooking forward to discussing this further!"
        }

    async def generate_quick_response(self, job: Dict, user_profile: Dict) -> str:
        """Generate a quick 2-3 sentence response for fast applications."""
        client, _model = await self._resolve()
        if not client:
            return f"I'm interested in this opportunity and have relevant experience. I can start immediately and deliver quality work. Let's discuss the details!"

        try:
            response = client.chat.completions.create(
                model=_model,
                messages=[
                    {
                        "role": "system",
                        "content": """Write a brief, punchy Upwork proposal opener (2-3 sentences max).
Be specific to the job. Don't be generic. Show you read the posting.
No fluff, no 'Dear client', just get straight to the point."""
                    },
                    {
                        "role": "user",
                        "content": f"""Job: {job.get('title')}
Description: {job.get('description', '')[:500]}
My skills: {', '.join(user_profile.get('skills', []))}

Write a quick response:"""
                    }
                ],
                temperature=0.8,
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Quick response generation failed: {e}")
            return f"I'm interested in this opportunity and have relevant experience. Let's discuss!"


ai_service = AIService()
