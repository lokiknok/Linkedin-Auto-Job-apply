import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Application, ApplicationStatus, JobListing
from application.workflow import application_workflow
from ai.question_answerer import question_answerer, AnswerSuggestion
from config import user_settings

logger = logging.getLogger("api.applications")
router = APIRouter(tags=["Applications"])


class CreateApplicationRequest(BaseModel):
    job_title: str
    company: str
    location: str
    job_url: str
    job_description: Optional[str] = None
    match_score: Optional[float] = 0.0
    application_status: Optional[str] = ApplicationStatus.FOUND.value
    notes: Optional[str] = None


class UpdateApplicationRequest(BaseModel):
    application_status: Optional[str] = None
    notes: Optional[str] = None
    resume_used: Optional[str] = None


class PrepareApplicationRequest(BaseModel):
    job_url: str


class MarkAppliedRequest(BaseModel):
    application_id: int
    notes: Optional[str] = None


class QuestionRequest(BaseModel):
    question: str
    job_title: Optional[str] = None
    job_description: Optional[str] = None
    company: Optional[str] = None


# -------------------------------------------------------------
# Dashboard Summary Stats
# -------------------------------------------------------------

@router.get("/api/dashboard/stats", response_model=Dict[str, Any])
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Returns application counts and metrics for the dashboard cards."""
    total_found = db.query(JobListing).count()
    apps = db.query(Application).all()

    total_tracked = len(apps)
    ready_to_submit = sum(1 for a in apps if a.application_status == ApplicationStatus.READY_TO_SUBMIT)
    reviewing = sum(1 for a in apps if a.application_status == ApplicationStatus.REVIEWING)
    applied = sum(1 for a in apps if a.application_status == ApplicationStatus.APPLIED)
    interviews = sum(1 for a in apps if a.application_status in (ApplicationStatus.INTERVIEW, ApplicationStatus.TECHNICAL_ROUND))
    offers = sum(1 for a in apps if a.application_status == ApplicationStatus.OFFER)
    rejected = sum(1 for a in apps if a.application_status == ApplicationStatus.REJECTED)
    withdrawn = sum(1 for a in apps if a.application_status == ApplicationStatus.WITHDRAWN)

    # Conversion rate
    conversion_rate = round((interviews / applied * 100), 1) if applied > 0 else 0.0

    return {
        "jobs_found": total_found,
        "total_tracked": total_tracked,
        "ready_to_submit": ready_to_submit,
        "reviewing": reviewing,
        "applied": applied,
        "interviews": interviews,
        "offers": offers,
        "rejected": rejected,
        "withdrawn": withdrawn,
        "conversion_rate_pct": conversion_rate
    }


# -------------------------------------------------------------
# Application CRUD Endpoints
# -------------------------------------------------------------

@router.get("/api/applications", response_model=Dict[str, Any])
def list_applications(
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lists tracked applications with optional status and search filters."""
    query = db.query(Application)

    if status and status.upper() != "ALL":
        try:
            status_enum = ApplicationStatus(status.upper())
            query = query.filter(Application.application_status == status_enum)
        except ValueError:
            pass

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Application.job_title.ilike(search_pattern)) |
            (Application.company.ilike(search_pattern)) |
            (Application.location.ilike(search_pattern))
        )

    apps = query.order_by(Application.updated_at.desc()).all()
    return {
        "count": len(apps),
        "applications": [a.to_dict() for a in apps]
    }


@router.get("/api/applications/{app_id}", response_model=Dict[str, Any])
def get_application(app_id: int, db: Session = Depends(get_db)):
    """Retrieves a single application by ID."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app.to_dict()


@router.post("/api/applications", response_model=Dict[str, Any])
def create_application(req: CreateApplicationRequest, db: Session = Depends(get_db)):
    """Creates a new application record. Prevents duplicates based on job URL."""
    existing = db.query(Application).filter(Application.job_url == req.job_url).first()
    if existing:
        return {
            "success": False,
            "message": "Application with this job URL already exists.",
            "application": existing.to_dict()
        }

    try:
        status_val = ApplicationStatus(req.application_status) if req.application_status else ApplicationStatus.FOUND
    except ValueError:
        status_val = ApplicationStatus.FOUND

    new_app = Application(
        job_title=req.job_title,
        company=req.company,
        location=req.location,
        job_url=req.job_url,
        job_description=req.job_description,
        match_score=req.match_score or 0.0,
        application_status=status_val,
        notes=req.notes,
        resume_used=user_settings.preferences.resume_path
    )
    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    return {
        "success": True,
        "message": "Application created successfully.",
        "application": new_app.to_dict()
    }


@router.patch("/api/applications/{app_id}", response_model=Dict[str, Any])
def update_application(app_id: int, req: UpdateApplicationRequest, db: Session = Depends(get_db)):
    """Updates status or notes on an application record."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if req.application_status:
        try:
            new_status = ApplicationStatus(req.application_status.upper())
            app.application_status = new_status
            if new_status == ApplicationStatus.APPLIED and not app.date_applied:
                app.date_applied = datetime.utcnow()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status value: {req.application_status}")

    if req.notes is not None:
        app.notes = req.notes

    if req.resume_used is not None:
        app.resume_used = req.resume_used

    app.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(app)

    return {
        "success": True,
        "message": "Application updated.",
        "application": app.to_dict()
    }


@router.delete("/api/applications/{app_id}", response_model=Dict[str, Any])
def delete_application(app_id: int, db: Session = Depends(get_db)):
    """Deletes an application record."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    db.delete(app)
    db.commit()
    return {"success": True, "message": "Application deleted."}


# -------------------------------------------------------------
# Application Workflow & AI Assistance Endpoints
# -------------------------------------------------------------

@router.post("/api/application/prepare", response_model=Dict[str, Any])
async def prepare_application_endpoint(req: PrepareApplicationRequest):
    """
    Triggers Playwright to open the job, fill standard fields, attach resume,
    and STOP before final submission for human review.
    """
    res = await application_workflow.prepare_application(req.job_url)
    return res


@router.post("/api/application/mark-applied", response_model=Dict[str, Any])
def mark_applied_endpoint(req: MarkAppliedRequest):
    """Marks an application as APPLIED in SQLite and broadcasts Telegram notification."""
    return application_workflow.mark_applied(req.application_id, req.notes)


@router.post("/api/application/question", response_model=Dict[str, Any])
async def answer_question_endpoint(req: QuestionRequest):
    """Provides AI/rule-based suggested answer for custom application questions."""
    suggestion = await question_answerer.answer_question(
        question=req.question,
        job_title=req.job_title,
        job_description=req.job_description,
        company=req.company
    )
    return {
        "success": True,
        "question": suggestion.question,
        "suggested_answer": suggestion.suggested_answer,
        "confidence": suggestion.confidence,
        "reasoning": suggestion.reasoning
    }

