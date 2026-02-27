import pytest
from datetime import date, timedelta
from app.models.onboarding_employee import OnboardingEmployee, OnboardingStatus
from app.models.onboarding_template import OnboardingTemplate
from app.models.onboarding_task import OnboardingTask, OnboardingTaskCategory
from app.models.department import Department

def test_create_template(client, admin_user, org, get_token):
    """Test template creation."""
    token = get_token(admin_user, org.id)
    payload = {
        "name": "General",
        "tasks": [{"task_name": "Task 1", "category": "documentation", "due_offset_days": -1}],
        "is_active": True
    }
    response = client.post("/api/onboarding/templates", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["name"] == "General"

def test_apply_template(client, admin_user, db_session, org, get_token):
    """Test applying template."""
    emp = OnboardingEmployee(
        employee_name="Hire", employee_email="hire@example.com", position="Dev",
        department="IT", start_date=date.today() + timedelta(days=7),
        organization_id=org.id, status=OnboardingStatus.pending
    )
    db_session.add(emp)
    db_session.commit()
    
    template = OnboardingTemplate(organization_id=org.id, name="Dev", tasks=[{"task_name": "T1", "due_offset_days": 1}], is_active=True)
    db_session.add(template)
    db_session.commit()
    
    token = get_token(admin_user, org.id)
    response = client.post(f"/api/onboarding/employees/{emp.id}/apply-template/{template.id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_progress_tracking(client, admin_user, db_session, org, get_token):
    """Test progress."""
    emp = OnboardingEmployee(
        employee_name="Charlie", employee_email="charlie@example.com", position="Dev",
        department="IT", start_date=date.today() + timedelta(days=7),
        organization_id=org.id, status=OnboardingStatus.pending
    )
    db_session.add(emp)
    db_session.commit()
    
    task = OnboardingTask(employee_id=emp.id, task_title="T1", is_completed=False, task_category=OnboardingTaskCategory.other)
    db_session.add(task)
    db_session.commit()
    
    token = get_token(admin_user, org.id)
    response = client.get(f"/api/onboarding/employees/{emp.id}/progress", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["completion_percentage"] == 0
    
    client.put(f"/api/onboarding/tasks/{task.id}/complete", headers={"Authorization": f"Bearer {token}"})
    response = client.get(f"/api/onboarding/employees/{emp.id}/progress", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["completion_percentage"] == 100
