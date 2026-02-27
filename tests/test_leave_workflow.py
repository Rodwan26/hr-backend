import pytest
from datetime import date, timedelta
from app.models.leave_request import LeaveRequest, LeaveStatus

def _create_leave_request(client, admin_user, org, get_token):
    start = date.today() + timedelta(days=10)
    end = start + timedelta(days=15)
    token = get_token(admin_user, org.id)
    response = client.post(
        "/api/leave/requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"start_date": start.isoformat(), "end_date": end.isoformat(), "leave_type": "Vacation"}
    )
    return response.json()["id"]

def _approve_leave_request(client, admin_user, org, get_token, req_id):
    token = get_token(admin_user, org.id)
    return client.post(
        "/api/leave/approve",
        headers={"Authorization": f"Bearer {token}"},
        json={"request_id": req_id, "approve": True, "comment": "Approved"}
    )

def test_create_leave_request(client, admin_user, org, get_token):
    """Test creating a leave request."""
    start = date.today() + timedelta(days=10)
    end = start + timedelta(days=15)
    token = get_token(admin_user, org.id)
    response = client.post(
        "/api/leave/requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"start_date": start.isoformat(), "end_date": end.isoformat(), "leave_type": "Vacation"}
    )
    assert response.status_code == 200

def test_manager_approval(client, admin_user, db_session, org, get_token):
    """Test manager approval."""
    req_id = _create_leave_request(client, admin_user, org, get_token)
    response = _approve_leave_request(client, admin_user, org, get_token, req_id)
    assert response.status_code == 200
    assert response.json()["leave_status"] == LeaveStatus.APPROVED

def test_calendar_view(client, admin_user, db_session, org, get_token):
    """Test calendar view."""
    req_id = _create_leave_request(client, admin_user, org, get_token)
    _approve_leave_request(client, admin_user, org, get_token, req_id)
    token = get_token(admin_user, org.id)
    response = client.get("/api/leave/calendar", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert len(response.json()) >= 1

def test_conflict_detection(client, admin_user, db_session, org, get_token):
    """Test overlap detection."""
    start = date.today() + timedelta(days=20)
    end = start + timedelta(days=25)
    token = get_token(admin_user, org.id)
    
    resp1 = client.post(
        "/api/leave/requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"start_date": start.isoformat(), "end_date": end.isoformat(), "leave_type": "Vacation"}
    )
    req_id = resp1.json()["id"]
    
    leave = db_session.get(LeaveRequest, req_id)
    leave.status = LeaveStatus.APPROVED
    db_session.commit()
    
    resp2 = client.post(
        "/api/leave/requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"start_date": (start + timedelta(days=2)).isoformat(), "end_date": (end + timedelta(days=2)).isoformat(), "leave_type": "Sick"}
    )
    assert resp2.json()["conflict_detected"] == True
