"""Deterministically ground word selections in the exact original passage."""

import re

from models.vocabulary_model import DifficultyLevel, IdentifiedWord, WordSelection

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
