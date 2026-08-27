import json
import logging
import re
from typing import Optional, Dict, Any, List
import httpx
from pydantic import BaseModel, Field
from config import env_settings, user_settings, UserProfile

logger = logging.getLogger("ai")


class AnswerSuggestion(BaseModel):
    question: str
    suggested_answer: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: Optional[str] = None


class AIQuestionAnswerer:
    """Generates suggested answers for custom job application questions using Gemini, OpenAI, or rule-based heuristics."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None
    ):
        if gemini_api_key is not None:
            self.gemini_api_key = gemini_api_key
        else:
            self.gemini_api_key = env_settings.GEMINI_API_KEY or env_settings.GOOGLE_API_KEY

        if openai_api_key is not None:
            self.openai_api_key = openai_api_key
        else:
            self.openai_api_key = env_settings.OPENAI_API_KEY

    @property
    def is_gemini_configured(self) -> bool:
        return bool(self.gemini_api_key and str(self.gemini_api_key).strip())

    @property
    def is_openai_configured(self) -> bool:
        return bool(self.openai_api_key and str(self.openai_api_key).strip())

    @property
    def is_configured(self) -> bool:
        return self.is_gemini_configured or self.is_openai_configured

    async def answer_question(
        self,
        question: str,
        job_title: Optional[str] = None,
        job_description: Optional[str] = None,
        company: Optional[str] = None,
        resume_text: Optional[str] = None,
        profile: Optional[UserProfile] = None
    ) -> AnswerSuggestion:
        """
        Generates suggested answer with confidence score.
        1. Checks user-configured custom QA pairs.
        2. Tries Gemini API if configured.
        3. Tries OpenAI API if configured.
        4. Falls back to intelligent rule-based heuristic matcher.
        """
        user_prof = profile or user_settings.profile

        # 1. First check direct user pre-configured Q&A
        if user_prof.custom_qa:
            norm_q = question.lower().strip()
            for stored_q, stored_a in user_prof.custom_qa.items():
                if stored_q.lower().strip() == norm_q or stored_q.lower() in norm_q or norm_q in stored_q.lower():
                    return AnswerSuggestion(
                        question=question,
                        suggested_answer=stored_a,
                        confidence=0.98,
                        reasoning="Exact match from user pre-configured custom Q&A."
                    )

        # 2. Try Gemini API
        if self.is_gemini_configured:
            gemini_ans = await self._call_gemini(
                question=question,
                job_title=job_title,
                job_description=job_description,
                company=company,
                resume_text=resume_text,
                profile=user_prof
            )
            if gemini_ans:
                return gemini_ans

        # 3. Try OpenAI API
        if self.is_openai_configured:
            openai_ans = await self._call_openai(
                question=question,
                job_title=job_title,
                job_description=job_description,
                company=company,
                resume_text=resume_text,
                profile=user_prof
            )
            if openai_ans:
                return openai_ans

        # 4. Fallback Rule-Based Heuristic Matcher
        return self._heuristic_answer(question, user_prof, job_title, company)

    async def _call_gemini(
        self,
        question: str,
        job_title: Optional[str],
        job_description: Optional[str],
        company: Optional[str],
        resume_text: Optional[str],
        profile: UserProfile
    ) -> Optional[AnswerSuggestion]:
        """Calls Google Gemini API for structured JSON question answering."""
        try:
            model = env_settings.GEMINI_MODEL or "gemini-2.5-flash"
            # Normalize model name for Google API endpoint
            model_endpoint = model.replace("models/", "")

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_endpoint}:generateContent?key={self.gemini_api_key}"

            system_instruction = (
                "You are a professional career assistant helping a job applicant draft accurate, polite, "
                "and compelling answers to application questions. "
                "Base your answers STRICTLY on the applicant's profile and resume provided. "
                "Do NOT fabricate experience or qualifications. "
                "Return a JSON object with: 'suggested_answer' (str), 'confidence' (float 0.0-1.0), 'reasoning' (str)."
            )

            prompt_content = f"""
System: {system_instruction}

Applicant Profile:
- Name: {profile.first_name} {profile.last_name}
- Years of Experience: {profile.years_of_experience}
- Skills: {', '.join(profile.skills)}
- Education: {profile.education_degree} in {profile.education_field} from {profile.education_school}
- Summary: {profile.summary}
- Location: {profile.location_city}, {profile.location_country}

Job Context:
- Target Job: {job_title or 'Software Engineer'} at {company or 'Company'}
- Job Description: {(job_description or '')[:400]}
- Resume Context: {(resume_text or '')[:400]}

Question:
{question}

Provide output strictly in JSON format:
{{"suggested_answer": "...", "confidence": 0.90, "reasoning": "..."}}
"""

            payload = {
                "contents": [
                    {
                        "parts": [{"text": prompt_content}]
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.2
                }
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text_part:
                            parsed = json.loads(text_part)
                            return AnswerSuggestion(
                                question=question,
                                suggested_answer=parsed.get("suggested_answer", ""),
                                confidence=float(parsed.get("confidence", 0.88)),
                                reasoning=parsed.get("reasoning", f"Generated using Google Gemini ({model}).")
                            )
                else:
                    logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"Gemini API generation failed: {e}. Falling back to heuristics.")

        return None

    async def _call_openai(
        self,
        question: str,
        job_title: Optional[str],
        job_description: Optional[str],
        company: Optional[str],
        resume_text: Optional[str],
        profile: UserProfile
    ) -> Optional[AnswerSuggestion]:
        """Calls OpenAI API for structured JSON question answering."""
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.openai_api_key)

            system_prompt = (
                "You are a professional career assistant helping a job applicant draft accurate, polite, "
                "and compelling answers to application questions. "
                "Base your answers STRICTLY on the applicant's profile and resume provided. "
                "Do NOT fabricate experience or qualifications. "
                "Provide output in strict JSON with fields: 'suggested_answer' (str), 'confidence' (float 0.0-1.0), 'reasoning' (str)."
            )

            user_context = {
                "applicant_name": f"{profile.first_name} {profile.last_name}",
                "years_of_experience": profile.years_of_experience,
                "skills": profile.skills,
                "education": f"{profile.education_degree} in {profile.education_field} from {profile.education_school}",
                "summary": profile.summary,
                "location": f"{profile.location_city}, {profile.location_country}",
                "target_job": f"{job_title or 'Engineer'} at {company or 'Company'}",
                "job_description_snippet": (job_description or "")[:500],
                "resume_summary": (resume_text or "")[:500],
                "question_to_answer": question
            }

            response = await client.chat.completions.create(
                model=env_settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_context, indent=2)}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=250
            )

            content = response.choices[0].message.content
            if content:
                parsed = json.loads(content)
                return AnswerSuggestion(
                    question=question,
                    suggested_answer=parsed.get("suggested_answer", ""),
                    confidence=float(parsed.get("confidence", 0.85)),
                    reasoning=parsed.get("reasoning", "Generated using OpenAI analysis.")
                )
        except Exception as e:
            logger.warning(f"OpenAI answer generation failed: {e}. Falling back to heuristic answerer.")

        return None

    def _heuristic_answer(
        self,
        question: str,
        profile: UserProfile,
        job_title: Optional[str] = None,
        company: Optional[str] = None
    ) -> AnswerSuggestion:
        """Rule-based heuristic pattern matching for common job application questions."""
        q_lower = question.lower()

        # Work Authorization / Sponsorship
        if "authorized to work" in q_lower or "legal right to work" in q_lower or "work authorization" in q_lower:
            return AnswerSuggestion(
                question=question,
                suggested_answer="Yes",
                confidence=0.95,
                reasoning="Standard affirmative work authorization."
            )

        if "require sponsorship" in q_lower or "visa sponsorship" in q_lower or "require visa" in q_lower:
            return AnswerSuggestion(
                question=question,
                suggested_answer="No",
                confidence=0.92,
                reasoning="Standard visa sponsorship response."
            )

        # Years of Experience / Skill Experience
        if "years of experience" in q_lower or "how many years" in q_lower:
            years = str(profile.years_of_experience)
            return AnswerSuggestion(
                question=question,
                suggested_answer=years,
                confidence=0.88,
                reasoning=f"Matched profile total experience of {years} years."
            )

        # Relocation
        if "willing to relocate" in q_lower or "open to relocation" in q_lower:
            return AnswerSuggestion(
                question=question,
                suggested_answer="Yes, I am open to relocation.",
                confidence=0.85,
                reasoning="Standard relocation preference."
            )

        # Notice period
        if "notice period" in q_lower or "how soon can you start" in q_lower or "earliest start date" in q_lower:
            return AnswerSuggestion(
                question=question,
                suggested_answer="Immediately / 15 days",
                confidence=0.85,
                reasoning="Standard availability timeframe."
            )

        # Expected Salary
        if "salary" in q_lower or "compensation" in q_lower or "expected ctc" in q_lower:
            return AnswerSuggestion(
                question=question,
                suggested_answer="Negotiable based on standard industry benchmarks and role responsibilities.",
                confidence=0.80,
                reasoning="Professional neutral salary negotiation response."
            )

        # Motivation / Why interested
        if "why are you interested" in q_lower or "why do you want to work" in q_lower or "why this role" in q_lower:
            target_role = job_title or "this position"
            target_co = company or "your organization"
            answer = (
                f"I am excited about {target_role} at {target_co} because it aligns directly with my background in "
                f"{', '.join(profile.skills[:4])}. I am eager to apply my technical skills and problem-solving "
                f"abilities to contribute to your team's success."
            )
            return AnswerSuggestion(
                question=question,
                suggested_answer=answer,
                confidence=0.82,
                reasoning="Template answer constructed from candidate skills and job title."
            )

        # Experience summary / Describe your experience
        if "describe your" in q_lower or "tell us about" in q_lower or "experience with" in q_lower:
            answer = (
                f"I have {profile.years_of_experience} years of hands-on experience working with "
                f"{', '.join(profile.skills[:5])}. {profile.summary}"
            )
            return AnswerSuggestion(
                question=question,
                suggested_answer=answer,
                confidence=0.78,
                reasoning="Constructed from profile summary and technical skills."
            )

        # Generic / Unknown Question
        return AnswerSuggestion(
            question=question,
            suggested_answer="",
            confidence=0.30,
            reasoning="Unrecognized custom question. Please review and provide manual input."
        )


# Global singleton QA instance
question_answerer = AIQuestionAnswerer()
