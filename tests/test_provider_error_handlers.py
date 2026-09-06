from fastapi.testclient import TestClient

from app.main import app
from app.provider.provider_errors import ProviderProtocolError, ProviderTimeoutError, ProviderUnavailableError
from app.service.agent_service import get_agent_service
from tests.test_agent_steps import step_request


class RaisingService:
    def execute_step(self, request):
        raise ProviderTimeoutError("secret upstream timeout detail")


def test_provider_timeout_maps_to_504_without_leaking_details():
    app.dependency_overrides[get_agent_service] = lambda: RaisingService()
    client = TestClient(app, raise_server_exceptions=False)

    try:
        response = client.post("/v1/agent/steps", json=step_request())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 504
    assert response.json() == {"detail": "Agent provider timed out."}
    assert "secret upstream timeout detail" not in response.text


class UnavailableService:
    def execute_step(self, request):
        raise ProviderUnavailableError("secret upstream unavailable detail")


def test_provider_unavailable_maps_to_502_without_leaking_details():
    app.dependency_overrides[get_agent_service] = lambda: UnavailableService()
    client = TestClient(app, raise_server_exceptions=False)

    try:
        response = client.post("/v1/agent/steps", json=step_request())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "Agent provider unavailable."}
    assert "secret upstream unavailable detail" not in response.text


class ProtocolErrorService:
    def execute_step(self, request):
        raise ProviderProtocolError("secret malformed provider payload")


def test_provider_protocol_error_maps_to_502_without_leaking_details():
    app.dependency_overrides[get_agent_service] = lambda: ProtocolErrorService()
    client = TestClient(app, raise_server_exceptions=False)

    try:
        response = client.post("/v1/agent/steps", json=step_request())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "Agent provider returned an invalid response."}
    assert "secret malformed provider payload" not in response.text
