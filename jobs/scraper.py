import asyncio
import logging
import re
import urllib.parse
from typing import List, Dict, Any, Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger("scraper")


class JobScraper:
    """Scrapes LinkedIn job listings from the search results page."""

    def __init__(self, page: Optional[Page] = None):
        self.page = page

    async def scrape_search_results(self, page: Page, max_cards: int = 25) -> List[Dict[str, Any]]:
        """Scrapes visible job cards from current LinkedIn job search page."""
        jobs: List[Dict[str, Any]] = []
        try:
            logger.info("Waiting for job cards to render...")
            # Wait for job container or job list item
            try:
                await page.wait_for_selector(
                    "li.jobs-search-results__list-item, div.job-card-container, ul.jobs-search__results-list li",
                    timeout=10000
                )
            except PlaywrightTimeoutError:
                logger.warning("No job card selector found within timeout.")
                return []

            # Scroll down slowly to trigger lazy loading of cards
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(1.0)

            # Query all cards
            card_elements = await page.query_selector_all(
                "li.jobs-search-results__list-item, div.job-card-container, div[data-job-id]"
            )
            logger.info(f"Found {len(card_elements)} candidate job elements.")

            for i, card in enumerate(card_elements[:max_cards]):
                try:
                    job_data = await self._parse_card(card, page)
                    if job_data and job_data.get("title") and job_data.get("url"):
                        jobs.append(job_data)
                except Exception as e:
                    logger.debug(f"Error parsing job card #{i}: {e}")

            logger.info(f"Successfully scraped {len(jobs)} jobs from search results.")
            return jobs

        except Exception as e:
            logger.error(f"Error during job search scraping: {e}")
            return []

    async def _parse_card(self, card, page: Page) -> Optional[Dict[str, Any]]:
        """Extracts title, company, location, url, and badges from a job card."""
        # Title & URL
        title_elem = await card.query_selector(
            "a.job-card-list__title--link, a.job-card-container__link, a[data-control-name='job_card_title'], a.base-card__full-link"
        )
        if not title_elem:
            return None

        title = (await title_elem.inner_text()).strip()
        url = await title_elem.get_attribute("href") or ""
        if url.startswith("/"):
            url = f"https://www.linkedin.com{url}"

        # Clean URL query tracking params
        clean_url = url.split("?")[0] if "?" in url else url

        # Job ID
        job_id = None
        id_attr = await card.get_attribute("data-job-id")
        if id_attr:
            job_id = id_attr
        else:
            match = re.search(r"view/(\d+)", url) or re.search(r"currentJobId=(\d+)", url)
            if match:
                job_id = match.group(1)

        # Company
        company_elem = await card.query_selector(
            ".job-card-container__primary-description, .base-search-card__subtitle, .job-card-container__company-name"
        )
        company = (await company_elem.inner_text()).strip() if company_elem else "Unknown Company"

        # Location
        location_elem = await card.query_selector(
            ".job-card-container__metadata-item, .job-search-card__location, .job-card-container__metadata-wrapper"
        )
        location = (await location_elem.inner_text()).strip() if location_elem else "Remote / Flexible"

        # Easy Apply badge detection
        easy_apply = False
        easy_apply_elem = await card.query_selector(
            ".job-card-container__apply-method, span:has-text('Easy Apply'), svg[data-test-icon='linkedin-bug']"
        )
        if easy_apply_elem:
            easy_apply = True

        # Snippet / Description snippet
        snippet_elem = await card.query_selector(".job-card-list__snippet, .job-card-container__job-insight")
        description = (await snippet_elem.inner_text()).strip() if snippet_elem else f"Job opportunity for {title} at {company}."

        return {
            "job_id": job_id or clean_url,
            "title": title,
            "company": company,
            "location": location,
            "url": clean_url,
            "description": description,
            "posted_date": "Recently posted",
            "employment_type": "Full-time",
            "experience_level": "Entry level",
            "easy_apply": easy_apply,
            "salary": None,
        }

    async def scrape_job_details(self, page: Page, job_url: str) -> Dict[str, Any]:
        """Opens a job URL and scrapes full description and details."""
        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(1.5)

            # Extract full job description
            desc_elem = await page.query_selector(
                ".jobs-description__content, .jobs-description-content__text, #job-details, .show-more-less-html__markup"
            )
            full_description = (await desc_elem.inner_text()).strip() if desc_elem else ""

            # Check for Easy Apply button
            apply_btn = await page.query_selector(
                "button.jobs-apply-button, button:has-text('Easy Apply')"
            )
            easy_apply = apply_btn is not None

            # Extract criteria (employment type, seniority)
            criteria_items = await page.query_selector_all(".jobs-description-details__list-item, .job-details-jobs-unified-top-card__job-insight")
            criteria_texts = []
            for item in criteria_items:
                criteria_texts.append((await item.inner_text()).strip())

            return {
                "description": full_description,
                "easy_apply": easy_apply,
                "criteria": criteria_texts
            }
        except Exception as e:
            logger.error(f"Error scraping detailed job info from {job_url}: {e}")
            return {"description": "", "easy_apply": True, "criteria": []}


def generate_mock_jobs(keywords: List[str], locations: List[str], count: int = 10) -> List[Dict[str, Any]]:
    """
    Generates realistic mock jobs for offline testing, verification, and UI demonstrations
    when the user has not launched a live LinkedIn session.
    """
    import random

    companies = [
        "Google Cloud AI", "Amazon Web Services", "Microsoft AI Research",
        "Meta Platforms", "NVIDIA AI Labs", "Infosys Technology",
        "TCS Digital", "Zoho Corporation", "Freshworks Inc", "Swiggy Engineering",
        "Razorpay Software", "Cred Technologies", "Flipkart Labs", "OpenAI Partner Tech"
    ]

    titles_pool = [
        "Python Developer", "AI Engineer", "Machine Learning Engineer",
        "Junior Python Backend Developer", "Full Stack AI Developer",
        "Data Scientist - NLP & LLM", "Senior Python Engineer",
        "FastAPI Backend Specialist", "Computer Vision / Deep Learning Engineer"
    ]

    sample_descriptions = [
        (
            "We are looking for a passionate Python Developer to build scalable backend services with FastAPI and PostgreSQL. "
            "Experience with Docker, REST APIs, SQL, and unit testing is highly desired. "
            "You will collaborate with cross-functional AI teams to deploy machine learning models."
        ),
        (
            "Join our cutting-edge AI Engineering group! Developing LLM-driven agents, PyTorch model pipelines, and high-performance Python services. "
            "Key skills: Python, Machine Learning, AI, TensorFlow, PyTorch, Docker, Git. "
            "Entry level to 2 years experience welcome."
        ),
        (
            "Machine Learning Engineer opening in our Applied AI division. "
            "Hands-on experience with Python, scikit-learn, PyTorch, data preprocessing, and API development. "
            "Experience with Playwright automation or web data extraction is a plus."
        ),
        (
            "Backend Developer (Python / FastAPI). Responsible for architecture, database schema design, and asynchronous job processing. "
            "Skills: Python, FastAPI, SQLite, SQLAlchemy, Docker, Redis, Microservices."
        )
    ]

    mock_jobs = []
    for i in range(count):
        title = random.choice(titles_pool)
        company = random.choice(companies)
        location = random.choice(locations) if locations else "Remote"
        desc = random.choice(sample_descriptions)
        exp_level = random.choice(["Entry level", "Associate", "Mid-Senior"])
        job_id = f"mock-{100000 + i}"
        url = f"https://www.linkedin.com/jobs/view/{job_id}/"

        mock_jobs.append({
            "job_id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "description": desc,
            "posted_date": f"{random.randint(1, 6)} days ago",
            "employment_type": "Full-time",
            "experience_level": exp_level,
            "easy_apply": True,
            "salary": "$75,000 - $110,000 / yr" if random.random() > 0.5 else None,
            "match_score": 0.0
        })

    return mock_jobs

