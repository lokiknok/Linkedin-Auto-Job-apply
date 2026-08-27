import re
from typing import List, Dict, Any, Set, Optional
from config import JobPreferences, UserProfile

EXPERIENCE_HIERARCHY = {
    "internship": 1,
    "entry level": 2,
    "entry": 2,
    "associate": 3,
    "junior": 2,
    "mid-senior": 4,
    "mid senior": 4,
    "mid-senior level": 4,
    "director": 5,
    "executive": 6
}


def normalize_text(text: str) -> str:
    """Lowercase and clean alphanumeric text."""
    if not text:
        return ""
    return re.sub(r"[^\w\s]", " ", text.lower()).strip()


def calculate_title_match(job_title: str, target_titles: List[str]) -> float:
    """Calculates Title Match Score (0 - 100)."""
    if not job_title or not target_titles:
        return 0.0

    clean_job = normalize_text(job_title)
    job_words = set(clean_job.split())

    best_score = 0.0
    for target in target_titles:
        clean_target = normalize_text(target)
        target_words = set(clean_target.split())

        if not target_words:
            continue

        # Exact match
        if clean_target == clean_job:
            return 100.0

        # Substring phrase match
        if clean_target in clean_job or clean_job in clean_target:
            score = 90.0
        else:
            # Word overlap (Jaccard / Token overlap)
            intersection = job_words.intersection(target_words)
            if intersection:
                score = (len(intersection) / len(target_words)) * 80.0
            else:
                score = 0.0

        if score > best_score:
            best_score = score

    return min(100.0, best_score)


def calculate_skill_match(description: str, job_title: str, target_skills: List[str]) -> float:
    """Calculates Skill / Keyword Match Score (0 - 100)."""
    if not target_skills:
        return 50.0  # neutral if no skills specified

    combined_text = normalize_text(f"{job_title} {description}")
    if not combined_text:
        return 0.0

    matched_count = 0
    for skill in target_skills:
        clean_skill = normalize_text(skill)
        if not clean_skill:
            continue

        # Check whole word / phrase match
        pattern = r"\b" + re.escape(clean_skill) + r"\b"
        if re.search(pattern, combined_text):
            matched_count += 1

    # Ratio of matched target skills
    ratio = matched_count / len(target_skills)
    # Scale: 50% or more skills matched yields ~100 score
    score = min(100.0, (ratio / 0.5) * 100.0)
    return score


def calculate_location_match(job_location: str, target_locations: List[str], remote_pref: bool) -> float:
    """Calculates Location Match Score (0 - 100)."""
    if not target_locations:
        return 80.0

    clean_job_loc = normalize_text(job_location)

    # If job is remote and user prefers remote
    if "remote" in clean_job_loc and remote_pref:
        return 100.0

    for loc in target_locations:
        clean_loc = normalize_text(loc)
        if not clean_loc:
            continue

        if clean_loc in clean_job_loc or clean_job_loc in clean_loc:
            return 100.0

        # Match city or state tokens
        loc_tokens = set(clean_loc.split())
        job_tokens = set(clean_job_loc.split())
        if loc_tokens.intersection(job_tokens):
            return 85.0

    if remote_pref and "remote" in [loc.lower() for loc in target_locations]:
        # User is open to remote, but job is onsite somewhere else
        return 40.0

    return 20.0


def calculate_experience_match(job_exp: Optional[str], target_exp: str) -> float:
    """Calculates Experience Match Score (0 - 100)."""
    if not job_exp or not target_exp:
        return 75.0  # neutral default

    clean_job_exp = normalize_text(job_exp)
    clean_target_exp = normalize_text(target_exp)

    if clean_target_exp in clean_job_exp or clean_job_exp in clean_target_exp:
        return 100.0

    job_level = EXPERIENCE_HIERARCHY.get(clean_job_exp, 2)
    target_level = EXPERIENCE_HIERARCHY.get(clean_target_exp, 2)

    diff = abs(job_level - target_level)
    if diff == 0:
        return 100.0
    elif diff == 1:
        return 75.0
    elif diff == 2:
        return 45.0
    else:
        return 20.0


def calculate_relevance_score(
    job: Dict[str, Any],
    preferences: JobPreferences,
    profile: Optional[UserProfile] = None
) -> float:
    """
    Calculates composite relevance score:
    - Title match:      40%
    - Skill match:      30%
    - Location match:   20%
    - Experience match: 10%
    """
    job_title = job.get("title") or job.get("job_title", "")
    description = job.get("description") or job.get("job_description", "")
    location = job.get("location", "")
    exp_level = job.get("experience_level", "")

    # Combine preferences keywords and user profile skills
    skills = list(preferences.keywords)
    if profile and profile.skills:
        for s in profile.skills:
            if s not in skills:
                skills.append(s)

    title_score = calculate_title_match(job_title, preferences.job_titles)
    skill_score = calculate_skill_match(description, job_title, skills)
    location_score = calculate_location_match(location, preferences.locations, preferences.remote)
    exp_score = calculate_experience_match(exp_level, preferences.experience_level)

    total_score = (
        (0.40 * title_score) +
        (0.30 * skill_score) +
        (0.20 * location_score) +
        (0.10 * exp_score)
    )
    return round(total_score, 1)


def filter_and_score_jobs(
    jobs: List[Dict[str, Any]],
    preferences: JobPreferences,
    profile: Optional[UserProfile] = None,
    existing_urls: Optional[Set[str]] = None
) -> List[Dict[str, Any]]:
    """Scores, filters duplicates, and orders jobs by relevance."""
    existing = existing_urls or set()
    filtered_jobs = []

    for job in jobs:
        url = job.get("url") or job.get("job_url", "")
        # Prevent duplicate applications based on job URL
        if url and url in existing:
            continue

        score = calculate_relevance_score(job, preferences, profile)
        job["match_score"] = score

        if score >= preferences.min_match_score:
            filtered_jobs.append(job)

    # Sort descending by match score
    filtered_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)

    # Limit to maximum jobs per session
    return filtered_jobs[: preferences.max_jobs_per_session]

