import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import JobListing, Application
from jobs.search import job_search_service

logger = logging.getLogger("api.jobs")
router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


class JobSearchRequest(BaseModel):
    keywords: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    use_mock_if_offline: bool = True


@router.get("", response_model=Dict[str, Any])
def list_jobs(
    min_score: float = Query(0.0, ge=0.0, le=100.0),
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lists discovered job listings with optional score and text filtering."""
    query = db.query(JobListing).filter(JobListing.match_score >= min_score)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (JobListing.title.ilike(search_pattern)) |
            (JobListing.company.ilike(search_pattern)) |
            (JobListing.location.ilike(search_pattern))
        )
    
    jobs = query.order_by(JobListing.match_score.desc()).all()
    return {
        "count": len(jobs),
        "jobs": [j.to_dict() for j in jobs]
    }


@router.get("/{job_id}", response_model=Dict[str, Any])
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Retrieves single job details by ID or URL."""
    job = db.query(JobListing).filter(
        (JobListing.id == int(job_id) if job_id.isdigit() else False) |
        (JobListing.job_id == job_id) |
        (JobListing.url == job_id)
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job listing not found")

    return job.to_dict()


@router.post("/search", response_model=Dict[str, Any])
async def trigger_job_search(req: JobSearchRequest):
    """Runs job search pipeline and returns newly discovered/ranked jobs."""
    try:
        results = await job_search_service.search_jobs(
            keywords=req.keywords,
            locations=req.locations,
            use_mock_if_offline=req.use_mock_if_offline
        )
        return {
            "success": True,
            "message": f"Discovered {len(results)} matching jobs.",
            "count": len(results),
            "jobs": results
        }
    except Exception as e:
        logger.error(f"Search endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

