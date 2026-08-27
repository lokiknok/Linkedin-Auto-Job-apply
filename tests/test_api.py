import pytest
from fastapi.testclient import TestClient
from app import app
from database.database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_get_and_update_settings():
    # GET Settings
    get_res = client.get("/api/settings")
    assert get_res.status_code == 200
    data = get_res.json()
    assert "profile" in data
    assert "preferences" in data

    # PUT Settings
    new_profile = data["profile"]
    new_profile["first_name"] = "Alice"
    update_res = client.put("/api/settings", json={"profile": new_profile})
    assert update_res.status_code == 200
    assert update_res.json()["settings"]["profile"]["first_name"] == "Alice"


def test_job_search_and_list():
    # Trigger Search (Mock / Offline Safe)
    search_res = client.post("/api/jobs/search", json={
        "keywords": ["Python Developer"],
        "locations": ["Chennai"],
        "use_mock_if_offline": True
    })
    assert search_res.status_code == 200
    data = search_res.json()
    assert data["success"] is True
    assert data["count"] > 0

    # List Jobs
    list_res = client.get("/api/jobs")
    assert list_res.status_code == 200
    assert list_res.json()["count"] > 0


def test_application_lifecycle():
    # Create Application
    create_payload = {
        "job_title": "FastAPI AI Developer",
        "company": "NextGen Labs",
        "location": "Remote",
        "job_url": "https://linkedin.com/jobs/view/test-lifecycle-101",
        "match_score": 92.0,
        "application_status": "FOUND",
        "notes": "Looks like an excellent match."
    }

    create_res = client.post("/api/applications", json=create_payload)
    assert create_res.status_code == 200
    app_data = create_res.json()["application"]
    app_id = app_data["id"]

    # Prevent Duplicate
    dup_res = client.post("/api/applications", json=create_payload)
    assert dup_res.status_code == 200
    assert dup_res.json()["success"] is False

    # Update Status
    patch_res = client.patch(f"/api/applications/{app_id}", json={
        "application_status": "READY_TO_SUBMIT",
        "notes": "Form prepared."
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["application"]["application_status"] == "READY_TO_SUBMIT"

    # Mark Applied
    mark_res = client.post("/api/application/mark-applied", json={
        "application_id": app_id,
        "notes": "Submitted manually on LinkedIn."
    })
    assert mark_res.status_code == 200
    assert mark_res.json()["application"]["application_status"] == "APPLIED"


def test_dashboard_stats():
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    stats = res.json()
    assert "jobs_found" in stats
    assert "total_tracked" in stats
    assert "ready_to_submit" in stats
    assert "applied" in stats


def test_ai_question_endpoint():
    res = client.post("/api/application/question", json={
        "question": "Are you legally authorized to work in this country?",
        "job_title": "Python Developer",
        "company": "Tech Corp"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["suggested_answer"] == "Yes"
    assert data["confidence"] >= 0.90

