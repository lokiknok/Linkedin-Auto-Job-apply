import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base
from database.models import Application, ApplicationStatus, JobListing


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_and_query_application(db_session):
    app = Application(
        job_title="Python Engineer",
        company="Example AI",
        location="Chennai",
        job_url="https://linkedin.com/jobs/view/999",
        job_description="FastAPI, Python",
        application_status=ApplicationStatus.FOUND,
        match_score=88.5
    )
    db_session.add(app)
    db_session.commit()

    saved = db_session.query(Application).filter(Application.job_url == "https://linkedin.com/jobs/view/999").first()
    assert saved is not None
    assert saved.job_title == "Python Engineer"
    assert saved.application_status == ApplicationStatus.FOUND
    assert saved.match_score == 88.5


def test_unique_job_url_constraint(db_session):
    app1 = Application(
        job_title="Dev 1",
        company="Company A",
        location="Remote",
        job_url="https://linkedin.com/jobs/view/dup",
        application_status=ApplicationStatus.FOUND
    )
    db_session.add(app1)
    db_session.commit()

    app2 = Application(
        job_title="Dev 2",
        company="Company B",
        location="Remote",
        job_url="https://linkedin.com/jobs/view/dup",
        application_status=ApplicationStatus.FOUND
    )
    db_session.add(app2)
    with pytest.raises(Exception):
        db_session.commit()


def test_application_status_transition(db_session):
    app = Application(
        job_title="AI Engineer",
        company="Innovate AI",
        location="Bangalore",
        job_url="https://linkedin.com/jobs/view/888",
        application_status=ApplicationStatus.READY_TO_SUBMIT
    )
    db_session.add(app)
    db_session.commit()

    app.application_status = ApplicationStatus.APPLIED
    db_session.commit()

    updated = db_session.query(Application).filter(Application.id == app.id).first()
    assert updated.application_status == ApplicationStatus.APPLIED

