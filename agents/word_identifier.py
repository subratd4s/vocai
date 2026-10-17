"""Prepare, request, and validate vocabulary without workflow orchestration."""

import json

from pydantic import ValidationError

from agents.prompts import identification_prompt
from agents.text_analyzer import InputValidationError, PreparedText, analyze_text
from agents.validator import validate_words
from models.vocabulary_model import DifficultyLevel, IdentificationResult, WordSelection
from services.llm_service import LLMService, LLMServiceError, StructuredLLM


def identify_words(
    text: str,
    difficulty: DifficultyLevel | str = DifficultyLevel.INTERMEDIATE,
    max_words: int = 10,
    *,
    llm: StructuredLLM | None = None,
) -> IdentificationResult:
    """One request per explicit invocation; metadata is never supplied by the LLM."""
    prepared = analyze_text(text)
    return identify_prepared_text(prepared, difficulty, max_words, llm=llm)


def identify_prepared_text(
    prepared: PreparedText,
    difficulty: DifficultyLevel | str,
    max_words: int,
    *,
    llm: StructuredLLM | None = None,
) -> IdentificationResult:
    """Reuse validated preparation in a workflow without analyzing text twice."""
    try:
        level = DifficultyLevel(difficulty)
    except (ValueError, TypeError):
        raise InputValidationError("Please select Beginner, Intermediate, or Advanced.") from None
    if type(max_words) is not int or not 1 <= max_words <= 20:
        raise InputValidationError("Please choose a maximum word count between 1 and 20.")
    selection = (llm if llm is not None else LLMService()).request_structured(
        identification_prompt(level, max_words),
        json.dumps({"passage": prepared.clean_text}, ensure_ascii=False),
        WordSelection,
    )
    try:
        selection = WordSelection.model_validate(selection)
    except ValidationError:
        raise LLMServiceError("The AI service returned an invalid structured response. Please try again.") from None
    return IdentificationResult(
        original_text=prepared.original_text,
        selected_difficulty=level,
        total_words_analyzed=prepared.word_count,
        identified_words=validate_words(selection, prepared.original_text, level, max_words),
    )
