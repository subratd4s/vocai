"""Batch contextual definitions through the existing structured LLM boundary."""

import json

from pydantic import ValidationError

from agents.prompts import DEFINITION_PROMPT
from models.vocabulary_model import DefinitionBatch, IdentifiedWord
from services.llm_service import LLMService, StructuredLLM, StructuredOutputError


def generate_definitions(
    words: list[IdentifiedWord],
    original_text: str,
    validation_errors: list[str] | None = None,
    *,
    llm: StructuredLLM | None = None,
) -> DefinitionBatch:
    """One batch request per attempt; no request for an empty selection."""
    if not words:
        return DefinitionBatch(entries=[])
    response = (llm if llm is not None else LLMService()).request_structured(
        DEFINITION_PROMPT,
        json.dumps({
            "passage": original_text,
            "identified_words": [word.model_dump(mode="json") for word in words],
            "validation_errors": validation_errors or [],
        }, ensure_ascii=False),
        DefinitionBatch,
    )
    try:
        return DefinitionBatch.model_validate(response)
    except ValidationError:
        raise StructuredOutputError(
            "Definition output must match the schema with nonempty definitions and example sentences."
        ) from None
