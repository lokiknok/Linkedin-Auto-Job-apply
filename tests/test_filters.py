import pytest
from config import JobPreferences, UserProfile
from jobs.filters import (
    calculate_title_match,
    calculate_skill_match,
    calculate_location_match,
    calculate_experience_match,
    calculate_relevance_score,
    filter_and_score_jobs
)


def test_title_match():
    targets = ["Python Developer", "AI Engineer"]

    # Exact match
    assert calculate_title_match("Python Developer", targets) == 100.0
    # Substring / partial match
    assert calculate_title_match("Senior Python Developer", targets) >= 80.0
    # Unrelated
    assert calculate_title_match("Registered Nurse", targets) == 0.0


def test_skill_match():
    skills = ["Python", "FastAPI", "SQL", "Docker"]
    desc = "We need a Python developer who knows FastAPI and SQL databases."
    score = calculate_skill_match(desc, "Backend Engineer", skills)
    assert score >= 50.0

    unrelated_desc = "Looking for a chef with culinary experience in pastry."
    assert calculate_skill_match(unrelated_desc, "Pastry Chef", skills) == 0.0


def test_location_match():
    locations = ["Chennai", "Bangalore", "Remote"]

    # Remote job when user allows remote
    assert calculate_location_match("Remote, India", locations, remote_pref=True) == 100.0
    # Exact city
    assert calculate_location_match("Chennai, Tamil Nadu", locations, remote_pref=True) == 100.0
    # Unknown location
    score = calculate_location_match("Berlin, Germany", locations, remote_pref=False)
    assert score <= 40.0


def test_experience_match():
    assert calculate_experience_match("Entry level", "Entry level") == 100.0
    assert calculate_experience_match("Associate", "Entry level") >= 70.0
    assert calculate_experience_match("Executive", "Entry level") <= 40.0


def test_composite_relevance_score():
    prefs = JobPreferences(
        job_titles=["Python Developer", "AI Engineer"],
        locations=["Chennai", "Remote"],
        keywords=["Python", "FastAPI", "Machine Learning"],
        experience_level="Entry level",
        remote=True
    )
    profile = UserProfile(
        skills=["Python", "FastAPI", "Machine Learning", "SQL"],
        years_of_experience=2
    )

    high_match_job = {
        "title": "Python Developer",
        "company": "Tech Corp",
        "location": "Chennai",
        "description": "Looking for a Python Developer with FastAPI and Machine Learning skills.",
        "experience_level": "Entry level",
        "url": "https://linkedin.com/jobs/view/101"
    }

    score = calculate_relevance_score(high_match_job, prefs, profile)
    assert score >= 85.0

    low_match_job = {
        "title": "HR Manager",
        "company": "Recruit Corp",
        "location": "London, UK",
        "description": "Handling payroll and talent acquisition.",
        "experience_level": "Mid-Senior",
        "url": "https://linkedin.com/jobs/view/102"
    }

    low_score = calculate_relevance_score(low_match_job, prefs, profile)
    assert low_score < 40.0


def test_deduplication_and_filtering():
    prefs = JobPreferences(min_match_score=50.0, max_jobs_per_session=5)
    existing_urls = {"https://linkedin.com/jobs/view/101"}

    raw_jobs = [
        {
            "title": "Python Developer",
            "company": "A",
            "location": "Remote",
            "description": "Python, FastAPI",
            "experience_level": "Entry level",
            "url": "https://linkedin.com/jobs/view/101"  # duplicate
        },
        {
            "title": "AI Engineer",
            "company": "B",
            "location": "Chennai",
            "description": "Python, Machine Learning, AI",
            "experience_level": "Entry level",
            "url": "https://linkedin.com/jobs/view/102"
        },
        {
            "title": "Marketing Associate",
            "company": "C",
            "location": "Tokyo",
            "description": "Sales",
            "experience_level": "Mid-Senior",
            "url": "https://linkedin.com/jobs/view/103"  # low score
        }
    ]

    filtered = filter_and_score_jobs(raw_jobs, prefs, existing_urls=existing_urls)
    urls = [j["url"] for j in filtered]

    # Duplicate 101 should be excluded
    assert "https://linkedin.com/jobs/view/101" not in urls
    # High match 102 should be included
    assert "https://linkedin.com/jobs/view/102" in urls

