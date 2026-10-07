from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_dead_letter_service, get_outbox_admin
from app.core.exceptions import OutboxEventNotFound
from app.main import create_app


@asynccontextmanager
async def _without_infrastructure(_app: FastAPI):
    yield


def test_health_and_auth_do_not_need_a_broker() -> None:
    with TestClient(create_app(_without_infrastructure)) as client:
        assert client.get("/health").json() == {"status": "ok"}

        missing = client.post("/api/v1/payments", json=_payload())
        assert missing.status_code == 401

        invalid = client.post("/api/v1/payments", headers={"X-API-Key": "wrong"}, json=_payload())
        assert invalid.status_code == 401

        missing_key = client.post(
            "/api/v1/payments",
            headers={"X-API-Key": "dev-api-key"},
            json=_payload(),
        )
        assert missing_key.status_code == 422

        unprocessable = client.post(
            "/api/v1/payments",
            headers={"X-API-Key": "dev-api-key", "Idempotency-Key": "order-1"},
            json=_payload(amount="-1"),
        )
        assert unprocessable.status_code == 422


def test_operations_endpoints_require_the_api_key() -> None:
    application = create_app(_without_infrastructure)
    application.dependency_overrides[get_outbox_admin] = lambda: _OutboxAdmin()
    application.dependency_overrides[get_dead_letter_service] = lambda: _DeadLetters()
    with TestClient(application) as client:
        assert client.get("/api/v1/outbox/failed").status_code == 401
        assert client.get("/api/v1/dead-letters").status_code == 401
        listed = client.get("/api/v1/outbox/failed", headers={"X-API-Key": "dev-api-key"})
        assert listed.status_code == 200
        assert listed.json() == []
        missing = client.post(
            "/api/v1/outbox/00000000-0000-0000-0000-000000000001/retry",
            headers={"X-API-Key": "dev-api-key"},
        )
        assert missing.status_code == 404


class _OutboxAdmin:
    async def list_failed(self):
        return []

    async def retry(self, event_id):
        raise OutboxEventNotFound(event_id)


class _DeadLetters:
    async def list_recent(self):
        return []


def _payload(amount: str = "10.00") -> dict:
    return {
        "amount": amount,
        "currency": "RUB",
        "description": "order",
        "metadata": {"order_id": "1"},
        "webhook_url": "https://example.com/hook",
    }
