"""Exercise the real Streamlit UI and provider-independent data contracts."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from models.vocabulary_model import VocabularyAnalysisResult, VocabularyEntry
from utils.helpers import count_words

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    return AppTest.from_file(str(APP_PATH), default_timeout=15).run()


@pytest.mark.parametrize("text, expected", [("", 0), (" \n\t ", 0), ("Hello, world!", 2), ("one\ntwo\tthree", 3)])
def test_count_words(text, expected):
    assert count_words(text) == expected


def test_launch_without_api_key(app):
    assert not app.exception
    assert app.text_area[0].value == ""
    assert app.button[2].label == "Download Definitions.txt"
    assert app.button[2].disabled
    assert app.session_state.analysis_result is None


@pytest.mark.parametrize("text", ["", " \n\t "])
def test_empty_submission(app, text):
    app.text_area[0].set_value(text).run()
    app.button[0].click().run()
    assert not app.exception
    assert "Please enter" in app.warning[0].value


def test_validation_edit_and_clear(app):
    app.text_area[0].set_value("Reading builds vocabulary.").run()
    assert app.caption[0].value == "Word count: 3"
    app.button[0].click().run()
    assert any(
        item.value == "Input validated successfully. AI vocabulary analysis will be implemented in Phase 2."
        for item in app.success
    )
    assert app.session_state.analysis_result is None
    app.run()
    assert app.text_area[0].value == "Reading builds vocabulary."
    app.text_area[0].set_value("New passage").run()
    assert app.session_state.validation_status is None
    app.button[0].click().run()
    app.button[1].click().run()
    assert not app.exception
    assert app.text_area[0].value == ""
    assert app.caption[0].value == "Word count: 0"
    assert app.session_state.validation_status is None
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
