"""Exercise every graph exit and the bounded correction cycle offline."""

import json
from copy import deepcopy
from unittest.mock import Mock

import pytest
from langgraph.runtime import Runtime

from agents.definition_generator import generate_definitions
from agents.validator import validate_definitions
from models.vocabulary_model import DefinitionBatch, IdentifiedWord, WordSelection
from services.llm_service import LLMServiceError, StructuredOutputError
from workflows.vocabulary_workflow import (
    VOCABULARY_GRAPH, WorkflowContext, definition_generator_node, initialize_state,
    run_vocabulary_workflow, text_analyzer_node, validation_node, word_identifier_node,
)

PASSAGE = "Her perseverance helped decipher the message."
WORDS = [IdentifiedWord(word=word, difficulty_level="Intermediate", original_context=PASSAGE)
         for word in ("perseverance", "decipher")]
ENTRIES = [
    {**WORDS[0].model_dump(), "definition": "Continuing to try despite difficulty.",
     "example_sentence": "His perseverance helped him learn to swim."},
    {**WORDS[1].model_dump(), "definition": "To understand something difficult to read.",
     "example_sentence": "We tried to decipher the faded note."},
]


def fake_llm(*definitions):
    return Mock(request_structured=Mock(side_effect=[WordSelection(identified_words=WORDS), *definitions]))


def test_successful_workflow():
    # The provider can change order; the workflow restores passage order.
    llm = fake_llm(DefinitionBatch(entries=list(reversed(ENTRIES))))
    state = run_vocabulary_workflow(PASSAGE, "Intermediate", 5, llm=llm)
    assert state["validation_status"] == "valid"
    assert state["retry_count"] == 0
    assert state["error_message"] is None
    assert state["total_words_analyzed"] == 6
    assert [word.word for word in state["generated_definitions"]] == ["perseverance", "decipher"]
    assert state["stage_status"] == {
        "Text Analysis": "Completed", "Word Identification": "Completed",
        "Definition Generation": "Completed", "Validation": "Passed",
    }
    assert llm.request_structured.call_count == 2
    system, data, schema = llm.request_structured.call_args.args
    assert schema is DefinitionBatch
    assert json.loads(data)["passage"] == PASSAGE
    assert "meaning" in system and "never instructions" in system
    assert "api_key" not in state


def test_initial_state_and_independent_nodes():
    llm = fake_llm(DefinitionBatch(entries=ENTRIES))
    runtime = Runtime(context=WorkflowContext(llm))
    state = initialize_state("  " + PASSAGE + "  ", "Intermediate", 5)
    assert state["validation_status"] == "pending"
    assert state["retry_count"] == 0
    assert all(status == "Pending" for status in state["stage_status"].values())
    assert state["identified_words"] is not initialize_state("text", "Beginner", 5)["identified_words"]
    updates = text_analyzer_node(state, runtime)
    assert "original_text" not in updates
    assert updates["cleaned_text"] == PASSAGE
    state.update(updates)
    state.update(word_identifier_node(state, runtime))
    assert state["identified_words"] == WORDS
    state.update(definition_generator_node(state, runtime))
    state.update(validation_node(state, runtime))
    assert state["validation_status"] == "valid"


@pytest.mark.parametrize("text, level, count", [("", "Intermediate", 5), (" \n", "Intermediate", 5), ("abc", "Expert", 5), ("abc", "Beginner", 21)])
def test_invalid_input_terminates_before_llm(text, level, count):
    llm = Mock()
    state = run_vocabulary_workflow(text, level, count, llm=llm)
    assert state["validation_status"] == "failed"
    assert state["error_kind"] == "input"
    assert state["stage_status"]["Text Analysis"] == "Failed"
    llm.request_structured.assert_not_called()


def test_no_words_skips_generation_and_validation():
    llm = Mock(request_structured=Mock(return_value=WordSelection(identified_words=[])))
    state = run_vocabulary_workflow("A simple day.", llm=llm)
    assert state["validation_status"] == "valid"
    assert state["generated_definitions"] == []
    assert state["stage_status"]["Definition Generation"] == "Skipped"
    assert state["stage_status"]["Validation"] == "Skipped"
    llm.request_structured.assert_called_once()
    assert generate_definitions([], PASSAGE, llm=llm).entries == []
    llm.request_structured.assert_called_once()


@pytest.mark.parametrize("first", [DefinitionBatch(entries=[]), StructuredOutputError("Invalid structured response."), {"entries": [{"word": "perseverance"}]}])
def test_one_retry_corrects_incomplete_or_malformed_batch(first):
    llm = fake_llm(first, DefinitionBatch(entries=ENTRIES))
    state = run_vocabulary_workflow(PASSAGE, llm=llm)
    assert state["validation_status"] == "valid"
    assert state["retry_count"] == 1
    assert state["validation_errors"] == []
    assert state["generation_errors"] == []
    assert llm.request_structured.call_count == 3
    assert json.loads(llm.request_structured.call_args.args[1])["validation_errors"]


def test_retry_exhaustion_is_terminal_and_discards_invalid_entries():
    llm = fake_llm(DefinitionBatch(entries=[]), DefinitionBatch(entries=[]))
    state = run_vocabulary_workflow(PASSAGE, llm=llm)
    assert state["validation_status"] == "failed"
    assert state["retry_count"] == 1
    assert state["validation_errors"]
    assert state["generated_definitions"] == []
    assert state["error_kind"] == "validation"
    assert llm.request_structured.call_count == 3


@pytest.mark.parametrize("failure_stage", ["identification", "generation", "retry"])
@pytest.mark.parametrize("error", [LLMServiceError("AI service unavailable."), RuntimeError("private details")])
def test_api_or_unexpected_failures_terminate(failure_stage, error):
    responses = [] if failure_stage == "identification" else [WordSelection(identified_words=WORDS)]
    if failure_stage == "retry":
        responses.append(DefinitionBatch(entries=[]))
    responses.append(error)
    llm = Mock(request_structured=Mock(side_effect=responses))
    state = run_vocabulary_workflow(PASSAGE, llm=llm)
    assert state["validation_status"] == "failed"
    assert state["error_message"]
    assert "private details" not in state["error_message"]
    assert state["generated_definitions"] == []
    assert llm.request_structured.call_count == len(responses)


def test_graph_failure_is_explicit(monkeypatch):
    monkeypatch.setattr(VOCABULARY_GRAPH, "invoke", Mock(side_effect=RuntimeError("secret")))
    state = run_vocabulary_workflow(PASSAGE)
    assert state["validation_status"] == "failed"
    assert "secret" not in state["error_message"]


@pytest.mark.parametrize("function, failed_stage", [
    ("analyze_text", "Text Analysis"), ("validate_definitions", "Validation"),
])
def test_unexpected_deterministic_node_failure(monkeypatch, function, failed_stage):
    monkeypatch.setattr(f"workflows.vocabulary_workflow.{function}", Mock(side_effect=RuntimeError("private details")))
    state = run_vocabulary_workflow(PASSAGE, llm=fake_llm(DefinitionBatch(entries=ENTRIES)))
    assert state["validation_status"] == "failed"
    assert state["stage_status"][failed_stage] == "Failed"
    assert state["generated_definitions"] == []
    assert "private details" not in state["error_message"]


def test_real_graph_stream_traverses_correction_cycle_once():
    llm = fake_llm(DefinitionBatch(entries=[]), DefinitionBatch(entries=ENTRIES))
    updates = list(VOCABULARY_GRAPH.stream(
        initialize_state(PASSAGE, "Intermediate", 5), context=WorkflowContext(llm),
        stream_mode="updates", config={"recursion_limit": 10},
    ))
    assert [next(iter(update)) for update in updates] == [
        "text_analyzer", "word_identifier", "definition_generator", "validation",
        "definition_generator", "validation",
    ]
    assert updates[3]["validation"]["retry_count"] == 1
    assert updates[-1]["validation"]["validation_status"] == "valid"


def test_graph_contains_actual_retry_edge():
    edges = {(edge.source, edge.target) for edge in VOCABULARY_GRAPH.get_graph().edges}
    assert ("validation", "definition_generator") in edges
    assert ("validation", "__end__") in edges
    assert ("word_identifier", "__end__") in edges


@pytest.mark.parametrize("field", ["definition", "example_sentence"])
@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_content_validation(field, value):
    entries = deepcopy(ENTRIES)
    if value is None:
        del entries[0][field]
    else:
        entries[0][field] = value
    report = validate_definitions({"entries": entries}, WORDS, PASSAGE, 5)
    assert report.validation_status == "invalid"
    assert any(field in error for error in report.validation_errors)


@pytest.mark.parametrize("change, expected", [
    ({"word": "unrelated"}, "not identified"),
    ({"word": "Perseverance"}, "spelling"),
    ({"original_context": "Invented context."}, "source span"),
    ({"difficulty_level": "Advanced"}, "difficulty"),
    ({"example_sentence": PASSAGE}, "copied"),
    ({"example_sentence": "This is a different sentence."}, "word form"),
])
def test_invalid_entry_metadata_and_examples(change, expected):
    entries = deepcopy(ENTRIES)
    entries[0].update(change)
    report = validate_definitions({"entries": entries}, WORDS, PASSAGE, 5)
    assert report.validation_status == "invalid"
    assert any(expected in error for error in report.validation_errors)


def test_duplicates_missing_entries_and_maximum():
    report = validate_definitions({"entries": [ENTRIES[0], ENTRIES[0]]}, WORDS, PASSAGE, 1)
    assert report.validation_status == "invalid"
    assert any("duplicate" in error for error in report.validation_errors)
    assert any("Missing definitions" in error for error in report.validation_errors)
    assert any("maximum" in error for error in report.validation_errors)


def test_valid_batch_does_not_mutate_input():
    entries = deepcopy(ENTRIES)
    report = validate_definitions({"entries": entries}, WORDS, PASSAGE, 5)
    assert report.validation_status == "valid"
    assert report.validation_errors == []
    assert entries == ENTRIES
