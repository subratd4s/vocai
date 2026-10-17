"""Offline tests using the real SDK parser with a mock HTTP transport."""

import json
from unittest.mock import Mock

import httpx
import pytest
from openai import OpenAI

from models.vocabulary_model import WordSelection
from services.llm_service import LLMService, LLMServiceError


def response_body(text='{"identified_words": []}', status="completed", refusal=False):
    content = {"type": "refusal", "refusal": "Cannot comply"} if refusal else {
        "type": "output_text", "text": text, "annotations": [],
    }
    return {
        "id": "resp_test", "object": "response", "created_at": 0,
        "model": "configured-model", "status": status,
        "output": [{"id": "msg_test", "type": "message", "role": "assistant",
                    "status": "completed", "content": [content]}],
    }


def install_transport(monkeypatch, handler):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-real")
    monkeypatch.setenv("OPENAI_MODEL", "configured-model")
    def factory(**kwargs):
        return OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    constructor = Mock(side_effect=factory)
    monkeypatch.setattr("services.llm_service.OpenAI", constructor)
    return constructor


def test_configured_model_and_real_sdk_structured_parser(monkeypatch):
    requests = []
    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=response_body())
    constructor = install_transport(monkeypatch, handler)
    result = LLMService().request_structured("system rules", '{"passage":"hello"}', WordSelection)
    assert result == WordSelection(identified_words=[])
    assert len(requests) == 1
    assert requests[0]["model"] == "configured-model"
    assert requests[0]["text"]["format"]["type"] == "json_schema"
    assert requests[0]["text"]["format"]["strict"] is True
    assert requests[0]["store"] is False
    assert requests[0]["input"][0]["role"] == "system"
    assert constructor.call_args.kwargs["timeout"] == 30.0
    assert constructor.call_args.kwargs["max_retries"] == 0


@pytest.mark.parametrize("key", ["", " ", "your_api_key_here"])
def test_missing_key(monkeypatch, key):
    monkeypatch.setenv("OPENAI_API_KEY", key)
    constructor = Mock()
    monkeypatch.setattr("services.llm_service.OpenAI", constructor)
    with pytest.raises(LLMServiceError, match="configure OPENAI_API_KEY"):
        LLMService().request_structured("rules", "data", WordSelection)
    constructor.assert_not_called()


@pytest.mark.parametrize("status, fragment", [(401, "rejected the API key"), (429, "rate limit"), (500, "could not complete"), (400, "model access")])
def test_api_status_errors(monkeypatch, status, fragment):
    handler = Mock(return_value=httpx.Response(status, json={"error": {"message": "private-details test-key-never-real"}}))
    install_transport(monkeypatch, handler)
    with pytest.raises(LLMServiceError, match=fragment) as error:
        LLMService().request_structured("rules", "data", WordSelection)
    assert "private-details" not in str(error.value)
    assert "test-key-never-real" not in str(error.value)
    handler.assert_called_once()


@pytest.mark.parametrize("exception, fragment", [(httpx.ConnectError, "Unable to connect"), (httpx.ReadTimeout, "timed out")])
def test_connection_errors(monkeypatch, exception, fragment):
    def handler(request):
        raise exception("private-details", request=request)
    install_transport(monkeypatch, handler)
    with pytest.raises(LLMServiceError, match=fragment):
        LLMService().request_structured("rules", "data", WordSelection)


@pytest.mark.parametrize("body", [response_body("not json"), response_body('{"wrong": []}'), response_body(refusal=True), response_body(status="incomplete"), {**response_body(), "output": []}])
def test_invalid_empty_refused_or_incomplete_response(monkeypatch, body):
    install_transport(monkeypatch, lambda request: httpx.Response(200, json=body))
    with pytest.raises(LLMServiceError):
        LLMService().request_structured("rules", "data", WordSelection)


def test_unexpected_error_is_sanitized(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("services.llm_service.OpenAI", Mock(side_effect=RuntimeError("private-details")))
    with pytest.raises(LLMServiceError, match="unexpected AI service error"):
        LLMService().request_structured("rules", "data", WordSelection)
