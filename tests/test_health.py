import pytest
from fastapi import status

def test_health_check(client):
    """Test the /health endpoint returns 200 and up status."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "up"
    assert "version" in data
    assert "timestamp" in data

def test_readiness_check(client):
    """Test the /readiness endpoint returns 200 and database status."""
    response = client.get("/readiness")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ready"
    assert data["components"]["database"] == "connected"

def test_root_endpoint(client):
    """Test the API root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "HR AI Platform API" in response.json()["message"]
