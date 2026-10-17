"""Compiled LangGraph workflow with invocation-local state and one correction."""

from dataclasses import dataclass
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from agents.definition_generator import generate_definitions
from agents.text_analyzer import InputValidationError, PreparedText, analyze_text
from agents.validator import validate_definitions
from agents.word_identifier import identify_prepared_text
from models.vocabulary_model import DifficultyLevel, IdentifiedWord, VocabularyEntry
from services.llm_service import LLMServiceError, StructuredLLM, StructuredOutputError

MAX_DEFINITION_RETRIES = 1
StageStatus = Literal["Pending", "Completed", "Passed", "Invalid", "Failed", "Skipped"]


class VocabularyState(TypedDict):
    original_text: str
    cleaned_text: str
    selected_difficulty: DifficultyLevel | str
    max_words: int
    total_words_analyzed: int
    identified_words: list[IdentifiedWord]
    generated_definitions: list[VocabularyEntry]
    validation_status: Literal["pending", "valid", "invalid", "failed"]
    validation_errors: list[str]
    generation_errors: list[str]
    retry_count: int
    error_message: str | None
    error_kind: Literal["input", "service", "validation", "unexpected"] | None
    stage_status: dict[str, StageStatus]


@dataclass(frozen=True)
class WorkflowContext:
    """Optional provider dependency, outside the shared state and its results."""

    llm: StructuredLLM | None = None


def initialize_state(text: str, difficulty: DifficultyLevel | str, max_words: int) -> VocabularyState:
    """Fresh containers per invocation; no results or secrets are shared."""
    return VocabularyState(
        original_text=text, cleaned_text="", selected_difficulty=difficulty,
        max_words=max_words, total_words_analyzed=0, identified_words=[],
        generated_definitions=[], validation_status="pending", validation_errors=[],
        generation_errors=[], retry_count=0, error_message=None, error_kind=None,
        stage_status={name: "Pending" for name in (
            "Text Analysis", "Word Identification", "Definition Generation", "Validation"
        )},
    )


def _stages(state: VocabularyState, **updates: StageStatus) -> dict[str, StageStatus]:
    return {**state["stage_status"], **updates}


def text_analyzer_node(state: VocabularyState, runtime: Runtime[WorkflowContext]) -> dict:
    prepared = analyze_text(state["original_text"])
    # Validate settings before the first billable request.
    try:
        level = DifficultyLevel(state["selected_difficulty"])
    except (ValueError, TypeError):
        raise InputValidationError("Please select Beginner, Intermediate, or Advanced.") from None
    if type(state["max_words"]) is not int or not 1 <= state["max_words"] <= 20:
        raise InputValidationError("Please choose a maximum word count between 1 and 20.")
    return {
        "cleaned_text": prepared.clean_text, "total_words_analyzed": prepared.word_count,
        "selected_difficulty": level,
        "stage_status": _stages(state, **{"Text Analysis": "Completed"}),
    }


def word_identifier_node(state: VocabularyState, runtime: Runtime[WorkflowContext]) -> dict:
    prepared = PreparedText(state["original_text"], state["cleaned_text"],
                            state["total_words_analyzed"], len(state["cleaned_text"]))
    result = identify_prepared_text(
        prepared, state["selected_difficulty"], state["max_words"], llm=runtime.context.llm,
    )
    updates = {
        "identified_words": result.identified_words,
        "stage_status": _stages(state, **{"Word Identification": "Completed"}),
    }
    if not result.identified_words:
        updates.update(validation_status="valid", stage_status=_stages(state, **{
            "Word Identification": "Completed", "Definition Generation": "Skipped", "Validation": "Skipped",
        }))
    return updates


def definition_generator_node(state: VocabularyState, runtime: Runtime[WorkflowContext]) -> dict:
    try:
        batch = generate_definitions(
            state["identified_words"], state["original_text"], state["validation_errors"],
            llm=runtime.context.llm,
        )
    except StructuredOutputError as error:
        return {
            "generated_definitions": [], "generation_errors": [str(error)],
            "stage_status": _stages(state, **{"Definition Generation": "Invalid"}),
        }
    return {
        "generated_definitions": batch.entries, "generation_errors": [],
        "stage_status": _stages(state, **{"Definition Generation": "Completed"}),
    }


def validation_node(state: VocabularyState, runtime: Runtime[WorkflowContext]) -> dict:
    report = validate_definitions(
        {"entries": state["generated_definitions"]}, state["identified_words"],
        state["original_text"], state["max_words"],
    )
    errors = state["generation_errors"] + report.validation_errors
    if not errors:
        by_word = {entry.word.casefold(): entry for entry in state["generated_definitions"]}
        return {
            "validation_status": "valid", "validation_errors": [],
            "generated_definitions": [by_word[word.word.casefold()] for word in state["identified_words"]],
            "stage_status": _stages(state, **{"Validation": "Passed"}),
        }
    if state["retry_count"] < MAX_DEFINITION_RETRIES:
        return {
            "validation_status": "invalid", "validation_errors": errors,
            "retry_count": state["retry_count"] + 1,
            "stage_status": _stages(state, **{"Validation": "Invalid"}),
        }
    return {
        "validation_status": "failed", "validation_errors": errors,
        "generated_definitions": [], "error_kind": "validation",
        "error_message": "Vocabulary validation failed after one correction attempt. Please try again.",
        "stage_status": _stages(state, **{"Validation": "Failed"}),
    }


def _guard(node, stage: str):
    """Convert node failures to explicit terminal state, without raw traces."""
    def guarded(state: VocabularyState, runtime: Runtime[WorkflowContext]) -> dict:
        try:
            return node(state, runtime)
        except InputValidationError as error:
            message, kind = str(error), "input"
        except LLMServiceError as error:
            message, kind = str(error), "service"
        except Exception:
            message, kind = "An unexpected workflow error occurred. Please try again later.", "unexpected"
        return {
            "validation_status": "failed", "generated_definitions": [],
            "error_message": message, "error_kind": kind,
            "stage_status": _stages(state, **{stage: "Failed"}),
        }
    return guarded


def route_after_analysis(state: VocabularyState) -> str:
    return END if state["error_message"] else "word_identifier"


def route_after_identification(state: VocabularyState) -> str:
    return END if state["error_message"] or not state["identified_words"] else "definition_generator"


def route_after_generation(state: VocabularyState) -> str:
    return END if state["error_message"] else "validation"


def route_after_validation(state: VocabularyState) -> str:
    return "definition_generator" if state["validation_status"] == "invalid" else END


def build_workflow():
    """Build actual conditional edges, including the bounded correction cycle."""
    graph = StateGraph(VocabularyState, context_schema=WorkflowContext)
    for name, node, stage in (
        ("text_analyzer", text_analyzer_node, "Text Analysis"),
        ("word_identifier", word_identifier_node, "Word Identification"),
        ("definition_generator", definition_generator_node, "Definition Generation"),
        ("validation", validation_node, "Validation"),
    ):
        graph.add_node(name, _guard(node, stage))
    graph.add_edge(START, "text_analyzer")
    graph.add_conditional_edges("text_analyzer", route_after_analysis, ["word_identifier", END])
    graph.add_conditional_edges("word_identifier", route_after_identification, ["definition_generator", END])
    graph.add_conditional_edges("definition_generator", route_after_generation, ["validation", END])
    graph.add_conditional_edges("validation", route_after_validation, ["definition_generator", END])
    return graph.compile()


VOCABULARY_GRAPH = build_workflow()


def run_vocabulary_workflow(
    text: str, difficulty: DifficultyLevel | str = DifficultyLevel.INTERMEDIATE,
    max_words: int = 10, *, llm: StructuredLLM | None = None,
) -> VocabularyState:
    """Invoke the reusable graph with isolated state and a safety recursion bound."""
    initial = initialize_state(text, difficulty, max_words)
    try:
        return VOCABULARY_GRAPH.invoke(initial, context=WorkflowContext(llm), config={"recursion_limit": 10})
    except Exception:
        return {**initial, "validation_status": "failed", "error_kind": "unexpected",
                "error_message": "The vocabulary workflow could not complete. Please try again later."}
