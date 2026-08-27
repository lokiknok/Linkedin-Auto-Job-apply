import enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, Enum as SAEnum
)
from database.database import Base


class ApplicationStatus(str, enum.Enum):
    FOUND = "FOUND"
    REVIEWING = "REVIEWING"
    READY_TO_SUBMIT = "READY_TO_SUBMIT"
    APPLIED = "APPLIED"
    INTERVIEW = "INTERVIEW"
    TECHNICAL_ROUND = "TECHNICAL_ROUND"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_title = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=False)
    job_url = Column(String(512), unique=True, nullable=False, index=True)
    job_description = Column(Text, nullable=True)
    application_status = Column(
        SAEnum(ApplicationStatus),
        default=ApplicationStatus.FOUND,
        nullable=False,
        index=True
    )
    match_score = Column(Float, default=0.0)
    employment_type = Column(String(100), nullable=True)
    experience_level = Column(String(100), nullable=True)
    easy_apply = Column(Boolean, default=True)
    salary_info = Column(String(100), nullable=True)
    date_found = Column(DateTime, default=datetime.utcnow, nullable=False)
    date_applied = Column(DateTime, nullable=True)
    resume_used = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    form_data = Column(Text, nullable=True)  # JSON serialized detected form data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_title": self.job_title,
            "company": self.company,
            "location": self.location,
            "job_url": self.job_url,
            "job_description": self.job_description,
            "application_status": self.application_status.value if self.application_status else ApplicationStatus.FOUND.value,
            "match_score": round(self.match_score, 1) if self.match_score is not None else 0.0,
            "employment_type": self.employment_type,
            "experience_level": self.experience_level,
            "easy_apply": self.easy_apply,
            "salary_info": self.salary_info,
            "date_found": self.date_found.isoformat() if self.date_found else None,
            "date_applied": self.date_applied.isoformat() if self.date_applied else None,
            "resume_used": self.resume_used,
            "notes": self.notes,
            "form_data": self.form_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class JobListing(Base):
    """Temporary storage/cache of discovered jobs before application preparation."""
    __tablename__ = "job_listings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String(100), unique=True, index=True, nullable=True)
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    url = Column(String(512), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    posted_date = Column(String(100), nullable=True)
    employment_type = Column(String(100), nullable=True)
    experience_level = Column(String(100), nullable=True)
    easy_apply = Column(Boolean, default=True)
    salary = Column(String(100), nullable=True)
    match_score = Column(Float, default=0.0)
    discovered_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "description": self.description,
            "posted_date": self.posted_date,
            "employment_type": self.employment_type,
            "experience_level": self.experience_level,
            "easy_apply": self.easy_apply,
            "salary": self.salary,
            "match_score": round(self.match_score, 1) if self.match_score is not None else 0.0,
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
        }

