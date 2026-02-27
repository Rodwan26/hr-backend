import pytest
import uuid
from datetime import datetime
from app.models.user import User, UserRole
from app.models.interview import Interview, InterviewStatus
from app.models.job import Job

def test_generate_slots(client, admin_user, db_session, org, get_token):
    """Test generating interview slots."""
    job = Job(title="Dev", department="IT", organization_id=org.id, is_active=True)
    db_session.add(job)
    db_session.commit()
    interview = Interview(
        organization_id=org.id,
        candidate_name="John",
        candidate_email="john@example.com",
        job_id=job.id,
        status=InterviewStatus.PENDING,
        interviewer_id=admin_user.id
    )
    db_session.add(interview)
    db_session.commit()
    token = get_token(admin_user, org.id)
    response = client.post(f"/api/interviews/{interview.id}/slots", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_generate_kit(client, admin_user, db_session, org, get_token):
    """Test generating interview kit."""
    job = Job(title="Dev", department="IT", organization_id=org.id, is_active=True)
    db_session.add(job)
    db_session.commit()
    interview = Interview(
        organization_id=org.id,
        candidate_name="Jane",
        candidate_email="jane@example.com",
        job_id=job.id,
        status=InterviewStatus.PENDING,
        interviewer_id=admin_user.id
    )
    db_session.add(interview)
    db_session.commit()
    token = get_token(admin_user, org.id)
    response = client.get(f"/api/interviews/{interview.id}/kit", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_submit_scorecard(client, admin_user, db_session, org, get_token):
    """Test submitting scorecard."""
    job = Job(title="Dev", department="IT", organization_id=org.id, is_active=True)
    db_session.add(job)
    db_session.commit()
    interview = Interview(
        organization_id=org.id,
        candidate_name="Bob",
        candidate_email="bob@example.com",
        job_id=job.id,
        status=InterviewStatus.PENDING,
        interviewer_id=admin_user.id
    )
    db_session.add(interview)
    db_session.commit()
    token = get_token(admin_user, org.id)
    payload = {
        "overall_rating": 4,
        "technical_score": 8,
        "communication_score": 9,
        "cultural_fit_score": 7,
        "strengths": ["test"],
        "concerns": ["none"],
        "feedback_text": "Good",
        "recommendation": "YES"
    }
    response = client.post(f"/api/interviews/{interview.id}/scorecard", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_consistency_check(client, admin_user, db_session, org, get_token):
    """Test consistency analysis."""
    job = Job(title="Dev", department="IT", organization_id=org.id, is_active=True)
    db_session.add(job)
    db_session.commit()
    interview = Interview(
        organization_id=org.id,
        candidate_name="Charlie",
        job_id=job.id,
        status=InterviewStatus.PENDING,
        interviewer_id=admin_user.id
    )
    db_session.add(interview)
    db_session.commit()
    token = get_token(admin_user, org.id)
    response = client.get(f"/api/interviews/{interview.id}/consistency", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_hiring_decision(client, admin_user, db_session, org, get_token):
    """Test final decision."""
    job = Job(title="Dev", department="IT", organization_id=org.id, is_active=True)
    db_session.add(job)
    db_session.commit()
    interview = Interview(
        organization_id=org.id,
        candidate_name="Dave",
        job_id=job.id,
        status=InterviewStatus.PENDING,
        interviewer_id=admin_user.id
    )
    db_session.add(interview)
    db_session.commit()
    token = get_token(admin_user, org.id)
    payload = {"status": "HIRED", "reason": "Good", "feedback_to_candidate": "Welcome"}
    response = client.post(f"/api/interviews/{interview.id}/decision", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
