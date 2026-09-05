import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.gemini_service import (
    GeminiService,
    GeminiNotConfiguredError,
    GeminiAuthenticationError,
    gemini_service,
)


def test_gemini_service_missing_key():
    """Test that GeminiService raises GeminiNotConfiguredError when no key is present."""
    service = GeminiService()
    # Force no key
    with pytest.raises(GeminiNotConfiguredError):
        service.get_client(override_key="")


def test_gemini_service_test_connection_missing_key():
    """Test test_connection returns proper diagnostic error dictionary on missing key."""
    service = GeminiService()
    res = service.test_connection(override_key="")
    assert res["success"] is False
    assert res["configured"] is False
    assert res["error_type"] == "NOT_CONFIGURED"
    assert "GEMINI_API_KEY" in res["message"]


def test_gemini_service_mocked_generation():
    """Test generate_chat_response with a mocked genai.Client."""
    service = GeminiService()
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Mocked Gemini Response for SRE triage."
    mock_chat.send_message.return_value = mock_response
    mock_client.chats.create.return_value = mock_chat

    with patch.object(service, "get_client", return_value=mock_client):
        reply = service.generate_chat_response(prompt="Status report")
        assert reply == "Mocked Gemini Response for SRE triage."
        mock_client.chats.create.assert_called_once()
        mock_chat.send_message.assert_called_once_with("Status report")


def test_chat_status_endpoint():
    """Test GET /api/chat/status returns status structure."""
    client = TestClient(app)
    res = client.get("/api/chat/status")
    assert res.status_code == 200
    data = res.json()
    assert "gemini_configured" in data
    assert "gemini_sdk" in data
    assert data["gemini_sdk"] == "google-genai"


def test_chat_gemini_test_endpoint_mocked():
    """Test GET /api/chat/gemini-test endpoint with mocked connection."""
    client = TestClient(app)
    mock_test_result = {
        "success": True,
        "configured": True,
        "model": "gemini-3.6-flash",
        "latency_ms": 120.5,
        "response": "Gemini API integration is online.",
        "sdk": "google-genai",
    }
    with patch.object(gemini_service, "test_connection", return_value=mock_test_result):
        res = client.get("/api/chat/gemini-test")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["model"] == "gemini-3.6-flash"
        assert data["sdk"] == "google-genai"
