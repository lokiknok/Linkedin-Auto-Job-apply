import asyncio
import logging
import urllib.parse
from typing import List, Dict, Any, Optional
from config import user_settings
from database.database import SessionLocal
from database.models import JobListing, Application
from browser.linkedin_browser import browser_manager
from jobs.scraper import JobScraper, generate_mock_jobs
from jobs.filters import filter_and_score_jobs
from telegram.notifier import telegram_notifier

logger = logging.getLogger("search")


def build_linkedin_search_url(
    keyword: str,
    location: str = "",
    remote: bool = False,
    easy_apply_only: bool = True,
    experience_level: Optional[str] = None
) -> str:
    """Builds a LinkedIn job search URL with query parameters."""
    params: Dict[str, Any] = {
        "keywords": keyword,
        "sortBy": "R"
    }

    if location:
        params["location"] = location

    if easy_apply_only:
        params["f_AL"] = "true"

    if remote:
        params["f_WT"] = "2"  # 2 = Remote

    exp_map = {
        "internship": "1",
        "entry level": "2",
        "associate": "3",
        "mid-senior": "4",
    }
    if experience_level and experience_level.lower() in exp_map:
        params["f_E"] = exp_map[experience_level.lower()]

    query_string = urllib.parse.urlencode(params)
    return f"https://www.linkedin.com/jobs/search/?{query_string}"


class JobSearchService:
    """Orchestrates job searching across targets, scoring, persistence, and notifications."""

    def __init__(self):
        self.scraper = JobScraper()

    async def search_jobs(
        self,
        keywords: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        use_mock_if_offline: bool = True
    ) -> List[Dict[str, Any]]:
        """Executes job searches, filters listings, saves results, and sends notifications."""
        prefs = user_settings.preferences
        profile = user_settings.profile

        search_titles = keywords or prefs.job_titles or ["Python Developer"]
        search_locations = locations or prefs.locations or ["Remote"]

        logger.info(f"Starting job search for: {search_titles} in {search_locations}")
        browser_manager.set_status("Searching for jobs...", "Job Search")

        all_raw_jobs: List[Dict[str, Any]] = []

        # Get existing URLs from DB to avoid duplicate entries
        db = SessionLocal()
        try:
            existing_app_urls = {row[0] for row in db.query(Application.job_url).all()}
            existing_listing_urls = {row[0] for row in db.query(JobListing.url).all()}
            all_existing_urls = existing_app_urls.union(existing_listing_urls)
        finally:
            db.close()

        # Check if browser is running and logged in
        is_live_browser = browser_manager.is_running and browser_manager.is_logged_in

        if is_live_browser:
            page = await browser_manager.get_page()
            if page:
                for title in search_titles[:3]:  # search up to 3 target titles
                    for loc in search_locations[:2]:
                        url = build_linkedin_search_url(
                            keyword=title,
                            location=loc,
                            remote=prefs.remote,
                            experience_level=prefs.experience_level
                        )
                        logger.info(f"Searching LinkedIn: {url}")
                        success = await browser_manager.navigate_to(url)
                        if success:
                            scraped = await self.scraper.scrape_search_results(page, max_cards=15)
                            all_raw_jobs.extend(scraped)
                            await asyncio.sleep(2)  # gentle pause between search navigations

        # If no live results found (or live browser not connected), generate mock demonstration jobs if permitted
        if not all_raw_jobs and use_mock_if_offline:
            logger.info("Using mock job generator for demonstration / offline validation.")
            all_raw_jobs = generate_mock_jobs(search_titles, search_locations, count=12)

        # Score, filter, and rank jobs
        filtered_jobs = filter_and_score_jobs(
            all_raw_jobs,
            preferences=prefs,
            profile=profile,
            existing_urls=existing_app_urls
        )

        logger.info(f"{len(all_raw_jobs)} jobs scraped, {len(filtered_jobs)} matched filters & threshold.")

        # Save new job listings to database
        db = SessionLocal()
        saved_jobs = []
        try:
            for j in filtered_jobs:
                url = j.get("url")
                existing = db.query(JobListing).filter(JobListing.url == url).first()
                if not existing:
                    listing = JobListing(
                        job_id=j.get("job_id"),
                        title=j.get("title"),
                        company=j.get("company"),
                        location=j.get("location"),
                        url=url,
                        description=j.get("description"),
                        posted_date=j.get("posted_date"),
                        employment_type=j.get("employment_type"),
                        experience_level=j.get("experience_level"),
                        easy_apply=j.get("easy_apply", True),
                        salary=j.get("salary"),
                        match_score=j.get("match_score", 0.0)
                    )
                    db.add(listing)
                    db.commit()
                    db.refresh(listing)
                    saved_jobs.append(listing.to_dict())

                    # Send Telegram notification if high match (>= 70%)
                    if j.get("match_score", 0) >= 70.0:
                        telegram_notifier.notify_job_found(j)
                else:
                    saved_jobs.append(existing.to_dict())
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving job listings to database: {e}")
        finally:
            db.close()

        browser_manager.set_status(f"Search complete: {len(saved_jobs)} jobs ready", "Ready")
        return saved_jobs if saved_jobs else filtered_jobs


# Global singleton job search service
job_search_service = JobSearchService()

