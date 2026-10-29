import pytest
from fastapi.testclient import TestClient
from backend.app.api.main import app
from backend.app.database import init_db, SessionLocal
from backend.app.services.sample_data_generator import generate_sample_dataset


@pytest.fixture(scope="module")
def client():
    init_db()
    db = SessionLocal()
    generate_sample_dataset(db, seed=42)
    db.close()
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_kpi_endpoint(client):
    res = client.get("/api/analytics/kpis?preset=last_30_days")
    assert res.status_code == 200
    data = res.json()
    assert "gross_sales" in data
    assert "net_sales" in data
    assert "units_sold" in data
    assert data["net_sales"]["current"] > 0


def test_products_endpoint(client):
    res = client.get("/api/analytics/products?limit=10&rank_by=units_sold")
    assert res.status_code == 200
    prods = res.json()
    assert len(prods) <= 10
    assert len(prods) > 0
    assert "units_sold" in prods[0]
    assert "classification" in prods[0]


def test_revenue_series_endpoint(client):
    res = client.get("/api/analytics/revenue-series?interval=daily")
    assert res.status_code == 200
    series = res.json()
    assert isinstance(series, list)


def test_insights_endpoint(client):
    res = client.get("/api/analytics/insights")
    assert res.status_code == 200
    insights = res.json()
    assert isinstance(insights, list)
    assert len(insights) > 0


def test_ai_summary_endpoint(client):
    res = client.get("/api/reports/ai-summary")
    assert res.status_code == 200
    summary = res.json()
    assert "report_markdown" in summary
    assert "Executive" in summary["report_markdown"]
