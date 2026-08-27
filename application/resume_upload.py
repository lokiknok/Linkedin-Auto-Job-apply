import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from config import RESUMES_DIR, user_settings

logger = logging.getLogger("resume")

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class ResumeManager:
    """Validates, manages, and extracts text from resume PDF files."""

    @staticmethod
    def validate_resume(file_path: Path) -> Tuple[bool, str]:
        """Validates that the file exists, is a PDF, and is under the size limit."""
        if not file_path.exists():
            return False, f"File does not exist: {file_path}"

        if not file_path.is_file():
            return False, f"Path is not a regular file: {file_path}"

        if file_path.suffix.lower() != ".pdf":
            return False, "Invalid file extension. Resume must be a .pdf file."

        file_size = file_path.stat().st_size
        if file_size == 0:
            return False, "File is empty (0 bytes)."

        if file_size > MAX_FILE_SIZE_BYTES:
            return False, f"File size ({round(file_size / (1024*1024), 2)} MB) exceeds 5 MB limit."

        # Verify PDF header magic bytes
        try:
            with open(file_path, "rb") as f:
                header = f.read(5)
                if not header.startswith(b"%PDF-"):
                    return False, "File is corrupted or not a valid PDF document."
        except Exception as e:
            return False, f"Error reading PDF header: {e}"

        return True, "Valid PDF resume."

    @staticmethod
    def save_uploaded_resume(filename: str, file_bytes: bytes) -> Dict[str, Any]:
        """Saves an uploaded resume PDF into the resumes directory and updates user settings."""
        if not filename.lower().endswith(".pdf"):
            return {"success": False, "message": "Only PDF files are supported."}

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            return {"success": False, "message": "File exceeds maximum size limit (5 MB)."}

        # Sanitize filename
        safe_filename = Path(filename).name
        target_path = RESUMES_DIR / safe_filename

        try:
            with open(target_path, "wb") as f:
                f.write(file_bytes)

            valid, msg = ResumeManager.validate_resume(target_path)
            if not valid:
                target_path.unlink(missing_ok=True)
                return {"success": False, "message": msg}

            # Update settings
            prefs = user_settings.preferences
            prefs.resume_path = str(target_path)
            user_settings.preferences = prefs

            logger.info(f"Resume saved successfully: {target_path}")
            return {
                "success": True,
                "message": "Resume uploaded and validated successfully.",
                "resume_path": str(target_path),
                "filename": safe_filename,
                "size_kb": round(len(file_bytes) / 1024, 1)
            }
        except Exception as e:
            logger.error(f"Failed to save resume: {e}")
            return {"success": False, "message": f"Upload error: {str(e)}"}

    @staticmethod
    def extract_text(file_path: Optional[str] = None) -> str:
        """Extracts plain text from resume PDF for AI context."""
        path_str = file_path or user_settings.preferences.resume_path
        if not path_str:
            return ""

        path = Path(path_str)
        if not path.exists():
            return ""

        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            text_pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_pages.append(text)
            return "\n".join(text_pages)
        except Exception as e:
            logger.warning(f"Could not extract text from PDF: {e}")
            return ""

    @staticmethod
    async def upload_to_playwright_input(page, input_selector: str = "input[type='file']") -> bool:
        """Attaches the configured resume to a Playwright file input element."""
        resume_path = user_settings.preferences.resume_path
        if not resume_path or not Path(resume_path).exists():
            logger.warning("No valid resume path configured in settings.")
            return False

        try:
            file_input = await page.query_selector(input_selector)
            if not file_input:
                # Try finding in modal
                file_input = await page.query_selector(".jobs-easy-apply-modal input[type='file']")

            if file_input:
                await file_input.set_input_files(str(Path(resume_path).resolve()))
                logger.info(f"Resume attached to form input: {resume_path}")
                return True
            else:
                logger.warning("File upload input element not found in application form.")
                return False
        except Exception as e:
            logger.error(f"Error uploading resume via Playwright: {e}")
            return False


resume_manager = ResumeManager()

