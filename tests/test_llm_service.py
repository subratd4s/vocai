"""Offline Gemini tests using the official SDK and a mock HTTP transport."""
import json
from unittest.mock import Mock

import httpx
import pytest
from google import genai

from models.vocabulary_model import DefinitionBatch, WordSelection
from services.llm_service import LLMService, LLMServiceError, StructuredOutputError


def response_body(text='{"identified_words": []}', finish="STOP"):
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": finish}]}


def install_transport(monkeypatch, handler):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-never-real")
    monkeypatch.setenv("GEMINI_MODEL", "configured-model")
    real_client = genai.Client
    def factory(**kwargs):
        kwargs['http_options'].httpx_client = httpx.Client(transport=httpx.MockTransport(handler))
        return real_client(**kwargs)
    constructor = Mock(side_effect=factory)
    monkeypatch.setattr("services.llm_service.genai.Client", constructor)
    return constructor


def test_configured_model_and_real_sdk_structured_parser(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=response_body())
    constructor = install_transport(monkeypatch, handler)
    result = LLMService().request_structured("system rules", '{"passage":"hello"}', WordSelection)
    assert result == WordSelection(identified_words=[])
    assert len(requests) == 1
    assert 'configured-model:generateContent' in requests[0].url.path
    body = json.loads(requests[0].content)
    assert body['generationConfig']['responseMimeType'] == 'application/json'
    assert 'identified_words' in body['generationConfig']['responseJsonSchema']['properties']
    assert body['generationConfig']['responseJsonSchema']['additionalProperties'] is False
    assert body['systemInstruction']['parts'][0]['text'] == 'system rules'
    assert body['contents'][0]['parts'][0]['text'] == '{"passage":"hello"}'
    options = constructor.call_args.kwargs['http_options']
    assert options.timeout == 30000
    assert options.retry_options.attempts == 3
    assert options.retry_options.http_status_codes == [503]
    assert constructor.call_args.kwargs['vertexai'] is False


@pytest.mark.parametrize('key', ['', ' ', 'your_api_key_here'])
def test_missing_key(monkeypatch, key):
    monkeypatch.setenv('GEMINI_API_KEY', key)
    constructor = Mock()
    monkeypatch.setattr('services.llm_service.genai.Client', constructor)
    with pytest.raises(LLMServiceError, match='configure GEMINI_API_KEY'):
        LLMService().request_structured('rules', 'data', WordSelection)
    constructor.assert_not_called()


@pytest.mark.parametrize('status, fragment', [(401,'rejected the API key'), (403,'rejected the API key'), (429,'rate limit'), (500,'could not complete'), (503,'temporarily overloaded'), (404,'model access'), (400,'model access'), (504,'timed out')])
def test_api_status_errors(monkeypatch, status, fragment):
    handler = Mock(return_value=httpx.Response(status, json={'error': {'code':status, 'message':'private-details test-key-never-real'}}))
    install_transport(monkeypatch, handler)
    with pytest.raises(LLMServiceError, match=fragment) as error:
        LLMService().request_structured('rules', 'data', WordSelection)
    assert 'private-details' not in str(error.value)
    assert 'test-key-never-real' not in str(error.value)
    assert handler.call_count == (3 if status == 503 else 1)


def test_transient_overload_recovers_without_charging_an_extra_workflow_step(monkeypatch):
    responses = [
        httpx.Response(503, json={'error': {'code': 503, 'message': 'busy'}}),
        httpx.Response(200, json=response_body()),
    ]
    handler = Mock(side_effect=responses)
    install_transport(monkeypatch, handler)
    assert LLMService().request_structured('rules', 'data', WordSelection) == WordSelection(identified_words=[])
    assert handler.call_count == 2


def test_invalid_key_bad_request(monkeypatch):
    install_transport(monkeypatch, lambda request: httpx.Response(400,json={'error':{'code':400,'message':'private','details':[{'reason':'API_KEY_INVALID'}]}}))
    with pytest.raises(LLMServiceError, match='rejected the API key'):
        LLMService().request_structured('rules','data',WordSelection)


@pytest.mark.parametrize('exception, fragment', [(httpx.ConnectError,'Unable to connect'), (httpx.ReadTimeout,'timed out')])
def test_connection_errors(monkeypatch, exception, fragment):
    def handler(request):
        raise exception('private-details',request=request)
    install_transport(monkeypatch, handler)
    with pytest.raises(LLMServiceError,match=fragment):
        LLMService().request_structured('rules','data',WordSelection)


@pytest.mark.parametrize('body', [response_body('not json'),response_body('{"wrong": []}'),response_body('', 'SAFETY'),response_body(finish='MAX_TOKENS'),{'candidates':[]},response_body('')])
def test_invalid_empty_refused_or_incomplete_response(monkeypatch, body):
    install_transport(monkeypatch, lambda request: httpx.Response(200,json=body))
    with pytest.raises(LLMServiceError):
        LLMService().request_structured('rules','data',WordSelection)


def test_unexpected_error_is_sanitized(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-key')
    monkeypatch.setattr('services.llm_service.genai.Client',Mock(side_effect=RuntimeError('private-details')))
    with pytest.raises(LLMServiceError,match='unexpected AI service error'):
        LLMService().request_structured('rules','data',WordSelection)


def test_real_sdk_parses_definition_batch(monkeypatch):
    payload={'entries':[{'word':'nuanced','definition':'Showing small differences.','original_context':'A nuanced account.','example_sentence':'Her nuanced explanation helped us.','difficulty_level':'Intermediate'}]}
    install_transport(monkeypatch,lambda request:httpx.Response(200,json=response_body(json.dumps(payload))))
    result=LLMService().request_structured('rules','data',DefinitionBatch)
    assert result.entries[0].word == 'nuanced'
    assert result.entries[0].definition == 'Showing small differences.'


def test_schema_failure_is_retryable(monkeypatch):
    install_transport(monkeypatch,lambda request:httpx.Response(200,json=response_body('{"entries": [{"word":"hello"}]}')))
    with pytest.raises(StructuredOutputError):
        LLMService().request_structured('rules','data',DefinitionBatch)


def test_empty_model_prevents_request(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-key')
    monkeypatch.setenv('GEMINI_MODEL',' ')
    constructor=Mock()
    monkeypatch.setattr('services.llm_service.genai.Client',constructor)
    with pytest.raises(LLMServiceError,match='configure GEMINI_MODEL'):
        LLMService().request_structured('rules','data',WordSelection)
    constructor.assert_not_called()
