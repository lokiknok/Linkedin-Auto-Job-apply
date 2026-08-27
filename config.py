import os
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
RESUMES_DIR = BASE_DIR / "resumes"
SETTINGS_FILE = DATA_DIR / "user_settings.json"

for directory in (DATA_DIR, LOGS_DIR, RESUMES_DIR):
    directory.mkdir(parents=True, exist_ok=True)


class UserProfile(BaseModel):
    first_name: str = "Candidate"
    last_name: str = "User"
    email: str = "user@example.com"
    phone: str = "+91 9876543210"
    linkedin_url: str = "https://www.linkedin.com/in/candidate"
    portfolio_url: Optional[str] = "https://github.com/candidate"
    location_city: str = "Chennai"
    location_state: str = "Tamil Nadu"
    location_country: str = "India"
    headline: str = "Software Engineer / AI Enthusiast"
    summary: str = "Experienced Python and AI Developer passionate about scalable systems."
    years_of_experience: int = 2
    education_degree: str = "Bachelor of Technology"
    education_field: str = "Computer Science"
    education_school: str = "University"
    skills: List[str] = [
        "Python", "FastAPI", "Machine Learning", "AI", "SQL",
        "Playwright", "Docker", "Git", "REST APIs"
    ]
    custom_qa: Dict[str, str] = {
        "Are you legally authorized to work in this country?": "Yes",
        "Will you now or in the future require sponsorship for employment visa status?": "No",
        "What is your expected salary?": "Negotiable based on market standard",
        "Are you willing to relocate?": "Yes",
        "How many years of experience do you have?": "2"
    }


class JobPreferences(BaseModel):
    job_titles: List[str] = [
        "Python Developer",
        "AI Engineer",
        "Machine Learning Engineer",
        "Backend Developer",
        "Data Scientist"
    ]
    locations: List[str] = [
        "Chennai",
        "Bangalore",
        "Remote",
        "India"
    ]
    keywords: List[str] = [
        "Python",
        "FastAPI",
        "Machine Learning",
        "AI",
        "PyTorch",
        "TensorFlow",
        "SQL",
        "Docker"
    ]
    experience_level: str = "Entry level"  # Internship, Entry level, Associate, Mid-Senior
    remote: bool = True
    hybrid: bool = True
    onsite: bool = True
    job_type: str = "Full-time"  # Full-time, Part-time, Contract, Internship
    max_jobs_per_session: int = 15
    min_match_score: float = 50.0
    resume_path: Optional[str] = None


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "LinkedIn Job Application Assistant"
    PORT: int = 8000
    HOST: str = "127.0.0.1"
    DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'applications.db'}"
    LOG_LEVEL: str = "INFO"

    # AI (Gemini & OpenAI support)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GOOGLE_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = "8855459956:AAEQYEvJ38OFDV7AkrfyfsSAGXU0N7eS4aM"
    TELEGRAM_CHAT_ID: Optional[str] = "6272891729"


# Global Settings Instance
env_settings = AppSettings()


class UserSettingsManager:
    """Manages persistent user settings stored in JSON."""
    def __init__(self, settings_path: Path = SETTINGS_FILE):
        self.settings_path = settings_path
        self._profile: UserProfile = UserProfile()
        self._preferences: JobPreferences = JobPreferences()
        self.load()

    def load(self):
        if self.settings_path.exists():
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "profile" in data:
                        self._profile = UserProfile(**data["profile"])
                    if "preferences" in data:
                        self._preferences = JobPreferences(**data["preferences"])
            except Exception as e:
                logging.error(f"Failed to load user settings: {e}")
        else:
            self.save()

    def save(self):
        try:
            data = {
                "profile": self._profile.model_dump(),
                "preferences": self._preferences.model_dump(),
            }
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save user settings: {e}")

    @property
    def profile(self) -> UserProfile:
        return self._profile

    @profile.setter
    def profile(self, value: UserProfile):
        self._profile = value
        self.save()

    @property
    def preferences(self) -> JobPreferences:
        return self._preferences

    @preferences.setter
    def preferences(self, value: JobPreferences):
        self._preferences = value
        self.save()

    def get_all(self) -> Dict[str, Any]:
        return {
            "profile": self._profile.model_dump(),
            "preferences": self._preferences.model_dump(),
            "telegram": {
                "configured": bool(env_settings.TELEGRAM_BOT_TOKEN and env_settings.TELEGRAM_CHAT_ID),
                "chat_id": env_settings.TELEGRAM_CHAT_ID or "",
            },
            "ai": {
                "configured": bool(env_settings.GEMINI_API_KEY or env_settings.GOOGLE_API_KEY or env_settings.OPENAI_API_KEY),
                "provider": "Google Gemini" if (env_settings.GEMINI_API_KEY or env_settings.GOOGLE_API_KEY) else ("OpenAI" if env_settings.OPENAI_API_KEY else "Heuristic / Rule-based"),
                "model": env_settings.GEMINI_MODEL if (env_settings.GEMINI_API_KEY or env_settings.GOOGLE_API_KEY) else (env_settings.OPENAI_MODEL if env_settings.OPENAI_API_KEY else "None")
            }
        }


user_settings = UserSettingsManager()


# Structured Logging Configuration
def setup_logging():
    log_level_name = env_settings.LOG_LEVEL.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(log_format, date_format)

    # Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicates
    if not root_logger.handlers:
        # File Handler (Rotating: 5MB max, 3 backups)
        log_file = LOGS_DIR / "app.log"
        file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

    # Suppress verbose 3rd party logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger("app")
