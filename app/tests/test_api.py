"""API endpoint tests"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestAPI:
    """Test API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_get_data(self, client):
        """Test data endpoint"""
        response = client.get("/data")
        assert response.status_code == 200

    def test_get_stats(self, client):
        """Test stats endpoint"""
        response = client.get("/stats")
        assert response.status_code == 200

    def test_data_with_filters(self, client):
        """Test data endpoint with filters"""
        response = client.get("/data?source=api&limit=10")
        assert response.status_code == 200

    def test_invalid_endpoint(self, client):
        """Test invalid endpoint returns 404"""
        response = client.get("/invalid")
        assert response.status_code == 404
