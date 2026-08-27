import logging
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException
from config import user_settings, UserProfile, JobPreferences
from application.resume_upload import resume_manager

logger = logging.getLogger("api.settings")
router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("", response_model=Dict[str, Any])
def get_settings():
    """Returns current user profile, preferences, and service configurations."""
    return user_settings.get_all()


@router.put("", response_model=Dict[str, Any])
def update_settings(payload: Dict[str, Any]):
    """Updates user profile and job preferences."""
    try:
        if "profile" in payload:
            user_settings.profile = UserProfile(**payload["profile"])
        if "preferences" in payload:
            user_settings.preferences = JobPreferences(**payload["preferences"])
        return {
            "success": True,
            "message": "Settings updated successfully.",
            "settings": user_settings.get_all()
        }
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resume", response_model=Dict[str, Any])
async def upload_resume(file: UploadFile = File(...)):
    """Uploads and validates a user's PDF resume."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resume files are accepted.")

    try:
        contents = await file.read()
        res = resume_manager.save_uploaded_resume(file.filename, contents)
        if not res["success"]:
            raise HTTPException(status_code=400, detail=res["message"])
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resume upload endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

