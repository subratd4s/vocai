"""Exercise the real Streamlit UI and provider-independent data contracts."""

from pathlib import Path
from unittest.mock import Mock

import pytest
import streamlit as st
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from models.vocabulary_model import DefinitionBatch, VocabularyAnalysisResult, VocabularyEntry, WordSelection
from services.llm_service import LLMService, LLMServiceError
from ui.presentation import shell
from utils.helpers import count_words

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def button(app, key):
    """Find an action by its stable key, independent of popover option buttons."""
    return next(item for item in app.button if item.key == key)


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
    button(app, "analyze").click().run()
    assert not app.exception
    assert "Please enter" in app.warning[0].value


def test_validation_edit_and_clear(app, monkeypatch):
    request = Mock(return_value=WordSelection(identified_words=[]))
    monkeypatch.setattr(LLMService, "request_structured", request)
    app.text_area[0].set_value("Reading builds vocabulary.").run()
    assert any(item.value == "3 words" for item in app.caption)
    button(app, "analyze").click().run()
    assert "No challenging vocabulary" in app.info[0].value
    assert app.session_state.analysis_result is not None
    assert app.session_state.download_content is None
    assert not app.download_button
    app.run()
    button(app, "analyze").click().run()
    assert request.call_count == 1
    assert app.text_area[0].value == "Reading builds vocabulary."
    app.text_area[0].set_value("New passage").run()
    assert app.session_state.validation_status is None
    button(app, "analyze").click().run()
    button(app, "clear").click().run()
    assert not app.exception
    assert app.text_area[0].value == ""
    assert any(item.value == "0 words" for item in app.caption)
    assert app.session_state.validation_status is None
    assert app.session_state.analysis_result is None
    assert app.session_state.download_content is None


@pytest.mark.parametrize("setting, value", [("difficulty", "Advanced"), ("max_words", 5)])
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
    assert app.session_state.difficulty == "Intermediate"
    assert app.session_state.max_words == 10
    app.text_area[0].set_value("A nuanced account.").run()
    button(app, "analyze").click().run()
    assert not app.exception
    metric_values = {metric.label: metric.value for metric in app.metric}
    assert metric_values["Words analyzed"] == "3"
    assert metric_values["Vocabulary discovered"] == "1"
    assert metric_values["Difficulty"] == "Intermediate"
    assert metric_values["Validation"] == "Passed"
    rendered_copy = " ".join(item.value for item in app.markdown)
    assert "Showing small differences." in rendered_copy
    assert "A nuanced account." in rendered_copy
    assert "She gave a nuanced explanation." in rendered_copy
    assert "Passed" in rendered_copy
    contents = app.session_state.download_content
    assert contents.decode("utf-8").strip() == app.code[0].value.strip()
    assert app.download_button[0].label == "Download file"
    assert app.download_button[0].proto.ignore_rerun
    _, download_kwargs = download_calls[-1]
    assert download_kwargs["file_name"] == "Definitions.txt"
    assert download_kwargs["mime"] == "text/plain"
    assert download_kwargs["data"] == contents
    app.download_button[0].click().run()
    assert not app.exception
    assert app.session_state.download_content == contents
    app.run()
    button(app, "analyze").click().run()
    assert request.call_count == 2
    app.session_state[setting] = value
    app.run()
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
    button(app, "analyze").click().run()
    assert not app.exception
    assert "after one correction" in app.error[0].value
    assert app.session_state.analysis_result is None
    assert app.session_state.workflow_state["validation_status"] == "failed"
    assert {metric.label for metric in app.metric} == set()
    assert not app.download_button
    assert "Validation" in " ".join(item.value for item in app.markdown)
    assert "Failed" in " ".join(item.value for item in app.markdown)
    app.run()
    assert request.call_count == 3
    button(app, "clear").click().run()
    assert app.session_state.workflow_state is None


def test_missing_key_in_ui(app):
    app.text_area[0].set_value("A meaningful passage.").run()
    button(app, "analyze").click().run()
    assert "GEMINI_API_KEY" in app.error[0].value
    assert not app.exception


@pytest.mark.parametrize("error", [LLMServiceError("Please try again."), RuntimeError("private details")])
def test_errors_do_not_show_tracebacks(app, monkeypatch, error):
    request = Mock(side_effect=error)
    monkeypatch.setattr(LLMService, "request_structured", request)
    app.text_area[0].set_value("A meaningful passage.").run()
    button(app, "analyze").click().run()
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


def test_reference_shell_is_minimal_with_fixed_bottom_bars():
    markup = shell(configured=True)
    assert 'class="rail"' in markup
    assert 'class="brand-name"' in markup and '>Vocai</a>' in markup
    assert 'class="bottom-bars"' in markup
    assert 'class="builder-info"' not in markup
    assert "utility-status" not in markup and "utility-help" not in markup
    assert "topbar" not in markup
