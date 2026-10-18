"""Exercise the real Streamlit UI and provider-independent data contracts."""

from pathlib import Path
from unittest.mock import Mock

import pytest
import streamlit as st
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from models.vocabulary_model import DefinitionBatch, VocabularyAnalysisResult, VocabularyEntry, WordSelection
from services.llm_service import LLMService, LLMServiceError
from utils.helpers import count_words

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    return AppTest.from_file(str(APP_PATH), default_timeout=15).run()


@pytest.mark.parametrize("text, expected", [("", 0), (" \n\t ", 0), ("Hello, world!", 2), ("one\ntwo\tthree", 3)])
def test_count_words(text, expected):
    assert count_words(text) == expected


def test_launch_without_api_key(app):
    assert not app.exception
    assert app.text_area[0].value == ""
    assert not app.download_button
    assert app.session_state.analysis_result is None


@pytest.mark.parametrize("text", ["", " \n\t "])
def test_empty_submission(app, text):
    app.text_area[0].set_value(text).run()
    app.button[0].click().run()
    assert not app.exception
    assert "Please enter" in app.warning[0].value


def test_validation_edit_and_clear(app, monkeypatch):
    request = Mock(return_value=WordSelection(identified_words=[]))
    monkeypatch.setattr(LLMService, "request_structured", request)
    app.text_area[0].set_value("Reading builds vocabulary.").run()
    assert app.caption[0].value == "3 words"
    app.button[0].click().run()
    assert "No challenging vocabulary" in app.info[0].value
    assert app.session_state.analysis_result is not None
    assert app.session_state.download_content is None
    assert not app.download_button
    app.run()
    app.button[0].click().run()
    assert request.call_count == 1
    assert app.text_area[0].value == "Reading builds vocabulary."
    app.text_area[0].set_value("New passage").run()
    assert app.session_state.validation_status is None
    app.button[0].click().run()
    app.button[1].click().run()
    assert not app.exception
    assert app.text_area[0].value == ""
    assert app.caption[0].value == "0 words"
    assert app.session_state.validation_status is None
    assert app.session_state.analysis_result is None
    assert app.session_state.download_content is None


@pytest.mark.parametrize("setting, value", [(0, "Advanced"), (1, 5)])
def test_settings_invalidate_results(app, monkeypatch, setting, value):
    download_calls = []
    original_download_button = st.download_button

    def capture_download(*args, **kwargs):
        download_calls.append((args, kwargs))
        return original_download_button(*args, **kwargs)

    monkeypatch.setattr(st, "download_button", capture_download)
    request = Mock(side_effect=[WordSelection(identified_words=[{
        "word": "nuanced", "difficulty_level": "Intermediate",
        "original_context": "A nuanced account.",
    }]), DefinitionBatch(entries=[VocabularyEntry(
        word="nuanced", difficulty_level="Intermediate", original_context="A nuanced account.",
        definition="Showing small differences.", example_sentence="She gave a nuanced explanation.",
    )])])
    monkeypatch.setattr(LLMService, "request_structured", request)
    assert app.selectbox[0].value == "Intermediate"
    assert app.selectbox[1].value == 10
    app.text_area[0].set_value("A nuanced account.").run()
    app.button[0].click().run()
    assert not app.exception
    assert [metric.value for metric in app.metric] == ["3", "1", "Intermediate"]
    assert app.text[0].value == "Showing small differences."
    assert app.text[1].value == "A nuanced account."
    assert app.text[2].value == "She gave a nuanced explanation."
    assert any(item.value == "Validation: Passed" for item in app.caption)
    contents = app.session_state.download_content
    assert contents.decode("utf-8").strip() == app.code[0].value.strip()
    assert app.download_button[0].label == "Download Definitions.txt"
    assert app.download_button[0].proto.ignore_rerun
    _, download_kwargs = download_calls[-1]
    assert download_kwargs["file_name"] == "Definitions.txt"
    assert download_kwargs["mime"] == "text/plain"
    assert download_kwargs["data"] == contents
    app.download_button[0].click().run()
    assert not app.exception
    assert app.session_state.download_content == contents
    app.run()
    app.button[0].click().run()
    assert request.call_count == 2
    app.selectbox[setting].select(value).run()
    assert app.session_state.analysis_result is None
    assert not app.metric
    assert not app.download_button
    assert app.session_state.download_content is None
    assert request.call_count == 2


def test_failed_definitions_are_not_displayed(app, monkeypatch):
    selection = WordSelection(identified_words=[{
        "word": "nuanced", "difficulty_level": "Intermediate", "original_context": "A nuanced account.",
    }])
    request = Mock(side_effect=[selection, DefinitionBatch(entries=[]), DefinitionBatch(entries=[])])
    monkeypatch.setattr(LLMService, "request_structured", request)
    app.text_area[0].set_value("A nuanced account.").run()
    app.button[0].click().run()
    assert not app.exception
    assert "after one correction" in app.error[0].value
    assert app.session_state.analysis_result is None
    assert app.session_state.workflow_state["validation_status"] == "failed"
    assert not app.metric
    assert not app.download_button
    assert any(item.value == "Validation: Failed" for item in app.caption)
    app.run()
    assert request.call_count == 3
    app.button[1].click().run()
    assert app.session_state.workflow_state is None


def test_missing_key_in_ui(app):
    app.text_area[0].set_value("A meaningful passage.").run()
    app.button[0].click().run()
    assert "GEMINI_API_KEY" in app.error[0].value
    assert not app.exception


@pytest.mark.parametrize("error", [LLMServiceError("Please try again."), RuntimeError("private details")])
def test_errors_do_not_show_tracebacks(app, monkeypatch, error):
    request = Mock(side_effect=error)
    monkeypatch.setattr(LLMService, "request_structured", request)
    app.text_area[0].set_value("A meaningful passage.").run()
    app.button[0].click().run()
    assert app.error
    assert "private details" not in app.error[0].value
    assert not app.exception
    assert app.session_state.analysis_result is None


def test_models_validate_and_round_trip():
    entry = VocabularyEntry(
        word=" nuanced ", definition="Showing subtle differences.",
        original_context="A nuanced understanding.",
        example_sentence="She gave a nuanced explanation.", difficulty_level="advanced",
    )
    result = VocabularyAnalysisResult(original_text="A nuanced understanding.", entries=[entry])
    assert result.entries[0].word == "nuanced"
    assert VocabularyAnalysisResult.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        VocabularyEntry.model_validate({**entry.model_dump(), "definition": "   "})
    with pytest.raises(ValidationError):
        VocabularyEntry.model_validate({**entry.model_dump(), "difficulty_level": "unknown"})
    with pytest.raises(ValidationError):
        VocabularyAnalysisResult(original_text=" ")


def test_analysis_entries_are_independent():
    first = VocabularyAnalysisResult(original_text="First passage")
    second = VocabularyAnalysisResult(original_text="Second passage")
    assert first.entries is not second.entries
