from fastapi.testclient import TestClient
import psycopg

from app import main
from app.models import Product


client = TestClient(main.app)


def sample_product() -> Product:
    return Product(
        sku="SMC-TEST-001",
        product_name="Test Controller",
        unit_price_usd=2.5,
        minimum_quantity=100,
        lead_time_weeks=4,
        supported_application="Automated testing",
        max_discount="10%",
    )


def test_ui_is_served():
    response = client.get("/")

    assert response.status_code == 200
    assert "QuoteBench" in response.text
    assert "Add product" in response.text
    assert "Run quote" in response.text
    assert "Run comparison" not in response.text


def test_list_products_returns_catalog_without_embeddings(monkeypatch):
    monkeypatch.setattr(main, "list_products", lambda: [sample_product()])

    response = client.get("/products")

    assert response.status_code == 200
    assert response.json()[0]["sku"] == "SMC-TEST-001"
    assert "embedding" not in response.json()[0]


def test_list_products_returns_empty_catalog(monkeypatch):
    monkeypatch.setattr(main, "list_products", lambda: [])

    response = client.get("/products")

    assert response.status_code == 200
    assert response.json() == []


def test_list_products_reports_database_unavailable(monkeypatch):
    def unavailable():
        raise psycopg.OperationalError("offline")

    monkeypatch.setattr(main, "list_products", unavailable)

    response = client.get("/products")

    assert response.status_code == 503
    assert response.json() == {"detail": "The product database is unavailable"}
