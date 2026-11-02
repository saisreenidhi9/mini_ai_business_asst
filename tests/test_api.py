"""
API and End-to-End Integration tests using FastAPI TestClient.
Tests request validation, endpoints, natural-language query resolution,
error responses, and metadata integrity.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """Create FastAPI TestClient instance."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    """Test GET /api/health returns operational status and database connection."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["database_connected"] is True
    assert data["total_records"] > 0
    assert data["valid_records"] > 0
    assert "version" in data


def test_summary_endpoint(client):
    """Test GET /api/summary returns validated business metrics."""
    response = client.get("/api/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["valid_transactions"] == 48
    assert data["total_completed_net_revenue"] == 1439200.0
    assert data["total_completed_gross_revenue"] == 1443700.0
    assert data["total_discounts"] == 4500.0
    assert data["total_units_sold"] == 633
    assert data["products_count"] == 7
    assert data["regions_count"] == 4
    assert data["excluded_records_count"] == 3
    assert len(data["data_quality_warnings"]) >= 3


def test_metadata_endpoint(client):
    """Test GET /api/metadata returns schema dimensions and available dates."""
    response = client.get("/api/metadata")
    assert response.status_code == 200
    data = response.json()
    assert "columns" in data
    assert "Transaction_Id" in [c.lower() for c in data["columns"]] or "transaction_id" in data["columns"]
    assert data["date_range"]["min_date"] == "2026-01-03"
    assert data["date_range"]["max_date"] == "2026-06-28"
    assert "2026-01" in data["available_months"]
    assert "2026-06" in data["available_months"]
    assert "Accessories" in data["product_categories"]
    assert "North" in data["regions"]


def test_ask_total_revenue(client):
    """Test Question 1: What is the total revenue?"""
    response = client.post("/api/ask", json={"question": "What is the total revenue?"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "total_revenue"
    assert data["metric"] == "net_revenue"
    assert data["value"] == 1439200.0
    assert data["unit"] == "currency units"
    assert "1,439,200.00" in data["answer"]
    assert len(data["supporting_data"]) > 0
    assert len(data["data_quality_notes"]) >= 3
    assert data["error"] is None


def test_ask_highest_revenue_product(client):
    """Test Question 2: Which product generated the highest revenue?"""
    response = client.post("/api/ask", json={"question": "Which product generated the highest revenue?"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "highest_revenue_product"
    assert data["metric"] == "net_revenue"
    assert "Monitor" in data["answer"]
    assert data["value"] == 473000.0
    assert data["chart"] is not None
    assert data["chart"]["chart_type"] == "bar"
    assert "Monitor" in data["chart"]["labels"]


def test_ask_monthly_revenue_trend(client):
    """Test Question 3: What is the monthly revenue trend?"""
    response = client.post("/api/ask", json={"question": "What is the monthly revenue trend?"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "monthly_revenue_trend"
    assert data["chart"] is not None
    assert data["chart"]["chart_type"] == "line"
    assert len(data["chart"]["labels"]) == 6
    assert data["value"] == 318500.0  # Peak revenue in May


def test_ask_highest_sales_region(client):
    """Test Question 4: Which region generated the highest sales?"""
    response = client.post("/api/ask", json={"question": "Which region generated the highest sales?"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "highest_sales_region"
    assert "South" in data["answer"]
    assert data["value"] == 411200.0
    assert data["chart"] is not None
    assert "South" in data["chart"]["labels"]


def test_ask_month_to_month_comparison(client):
    """Test Question 5: How did revenue change between two months?"""
    response = client.post(
        "/api/ask",
        json={"question": "How did revenue change between January and February?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "revenue_change_between_months"
    assert "increased" in data["answer"]
    assert data["value"] == 24350.0  # 234600 - 210250 = 24350
    assert data["chart"] is not None


def test_ask_month_comparison_alternative_syntax(client):
    """Test Question 5 variations: Compare revenue in March and April."""
    response = client.post(
        "/api/ask",
        json={"question": "Compare revenue in March and April"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "revenue_change_between_months"
    # March: 223900, April: 240700 -> Increase of 16800.0
    assert data["value"] == 16800.0
    assert "increased" in data["answer"]


def test_ask_empty_question_rejected(client):
    """Test that empty questions are rejected with 400 Bad Request."""
    response = client.post("/api/ask", json={"question": ""})
    # Pydantic min_length=1 catches empty string with 422, or endpoint catches with 400
    assert response.status_code in [400, 422]


def test_ask_whitespace_question(client):
    """Test that whitespace-only questions return structured invalid response or 400."""
    response = client.post("/api/ask", json={"question": "   "})
    assert response.status_code in [200, 400]
    if response.status_code == 200:
        data = response.json()
        assert data["intent"] == "invalid"
        assert data["error"] is not None


def test_ask_unsupported_question(client):
    """Test that unsupported questions return structured guidance without crashing."""
    response = client.post("/api/ask", json={"question": "What is the capital of France?"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "unsupported"
    assert data["error"] is not None
    assert "supported questions" in data["error"].lower()


def test_ask_missing_field_rejected(client):
    """Test that requests missing the required question field return 422."""
    response = client.post("/api/ask", json={})
    assert response.status_code == 422


def test_ask_incomplete_month_comparison(client):
    """Test asking for month comparison with only one month specified."""
    response = client.post(
        "/api/ask",
        json={"question": "How did revenue change in January?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "revenue_change_between_months"
    assert data["error"] is not None
    assert "provide two months" in data["error"].lower()


def test_frontend_root_served(client):
    """Test GET / serves frontend index.html."""
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>Mini AI Business Intelligence Assistant</title>" in response.text
