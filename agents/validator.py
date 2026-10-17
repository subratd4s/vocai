"""Deterministically ground word selections in the exact original passage."""

import re
from typing import Literal

from pydantic import BaseModel, ValidationError

from models.vocabulary_model import DefinitionBatch, DifficultyLevel, IdentifiedWord, WordSelection

# Apostrophes and hyphens connect words: do not match 'art' inside 'art-like'.
TOKEN = re.compile(r"\w+(?:['’\-]\w+)*", re.UNICODE)
WORD = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)


def validate_words(selection: WordSelection, original: str, level: DifficultyLevel, maximum: int) -> list[IdentifiedWord]:
    """Discard absent forms; replace model context with source-extracted spans."""
    first_occurrences = {}
    for match in TOKEN.finditer(original):
        if WORD.fullmatch(match.group()):
            first_occurrences.setdefault(match.group().casefold(), match)
    selected = {}
    for candidate in selection.identified_words:
        key = candidate.word.strip().casefold()
        if key in first_occurrences:
            selected[key] = first_occurrences[key]
    result = []
    for match in sorted(selected.values(), key=lambda item: item.start())[:maximum]:
        # Lightweight sentence spans, retaining punctuation and original whitespace.
        start = max(original.rfind(mark, 0, match.start()) for mark in ".!?\n") + 1
        ends = [pos for mark in ".!?\n" if (pos := original.find(mark, match.end())) >= 0]
        end = min(ends) + 1 if ends else len(original)
        result.append(IdentifiedWord(
            word=match.group(), difficulty_level=level,
            original_context=original[start:end].strip(),
        ))
    return result


class ValidationReport(BaseModel):
    """Structural and lightweight example checks, not factual verification."""

    validation_status: Literal["valid", "invalid", "failed"]
    validation_errors: list[str]


def validate_definitions(
    generated: object,
    identified: list[IdentifiedWord],
    original_text: str,
    max_words: int,
) -> ValidationReport:
    """Check completeness, source identity, and simple example constraints."""
    try:
        batch = DefinitionBatch.model_validate(generated)
    except ValidationError as error:
        # Include field paths and error kinds, never raw provider values.
        errors = [
            f"Schema error at {'.'.join(map(str, item['loc']))}: {item['type']}."
            for item in error.errors(include_input=False, include_url=False)
        ]
        return ValidationReport(validation_status="invalid", validation_errors=errors)
    errors = []
    expected = {word.word.casefold(): word for word in identified}
    seen = set()
    if len(batch.entries) > max_words:
        errors.append("Generated word count exceeds the configured maximum.")
    for index, entry in enumerate(batch.entries, 1):
        key = entry.word.casefold()
        if key in seen:
            errors.append(f"Entry {index}: duplicate vocabulary word.")
        seen.add(key)
        source = expected.get(key)
        if source is None:
            errors.append(f"Entry {index}: word was not identified in the passage.")
            continue
        if entry.word != source.word:
            errors.append(f"Entry {index}: preserve the original spelling and capitalization.")
        if entry.original_context != source.original_context or entry.original_context not in original_text:
            errors.append(f"Entry {index}: original context must match the supplied source span exactly.")
        if entry.difficulty_level != source.difficulty_level:
            errors.append(f"Entry {index}: difficulty level must match the identified word.")
        example = " ".join(entry.example_sentence.split()).casefold()
        passage = " ".join(original_text.split()).casefold()
        if example in passage:
            errors.append(f"Entry {index}: example sentence must be new, not copied from the passage.")
        if key not in {match.group().casefold() for match in TOKEN.finditer(entry.example_sentence)}:
            errors.append(f"Entry {index}: example sentence must contain the identified word form.")
    missing = len(set(expected) - seen)
    if missing:
        errors.append(f"Missing definitions for {missing} identified word(s); return every supplied word.")
    return ValidationReport(
        validation_status="invalid" if errors else "valid", validation_errors=errors,
    )
