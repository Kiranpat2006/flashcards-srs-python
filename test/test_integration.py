
# tests/test_integration.py

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Start the application and run its lifecycle hooks."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_postgres_and_redis(client):
    """Both real backing services must be healthy."""
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["postgres"] is True
    assert data["redis"] is True


def test_decks_endpoint_returns_decks(client):
    """The demo user should be able to retrieve their decks."""
    response = client.get("/decks", params={"user": "demo"})

    assert response.status_code == 200
    assert isinstance(response.json(), (list, dict))


def test_due_endpoint_returns_success(client):
    """Due cards should be retrieved from the database."""
    response = client.get("/study/demo/due")

    assert response.status_code == 200
    assert isinstance(response.json(), (list, dict))


def test_stats_endpoint_returns_success(client):
    """Study statistics should be available for the demo user."""
    response = client.get("/stats/demo")

    assert response.status_code == 200
    assert isinstance(response.json(), (list, dict))


def test_study_queue_and_answer_flow(client):
    """Start a study session and answer the next available card."""
    start_response = client.post(
        "/study/demo/start",
        params={"deck_id": 1},
    )

    assert start_response.status_code in (200, 201)

    next_response = client.get("/study/demo/next")
    assert next_response.status_code == 200

    card = next_response.json()

    # Support either a direct card object or a wrapped response.
    if isinstance(card, dict) and "card" in card:
        card = card["card"]

    assert isinstance(card, dict)

    card_id = card.get("card_id", card.get("id"))
    assert card_id is not None, "Next-card response must contain a card ID"

    answer_response = client.post(
        "/study/demo/answer",
        json={"card_id": card_id, "grade": 4},
    )

    assert answer_response.status_code in (200, 201)
