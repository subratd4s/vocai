"""Lightweight input preparation without LLM requests."""

import os
import re
from dataclasses import dataclass

from utils.config import load_environment
from utils.helpers import count_words


class InputValidationError(ValueError):
    """A safe, user-facing validation message."""


@dataclass(frozen=True)
class PreparedText:
    original_text: str
    clean_text: str
    word_count: int
    character_count: int


def analyze_text(text: str, max_length: int | None = None) -> PreparedText:
    """Validate raw length and normalize whitespace while retaining the source."""
    if not isinstance(text, str) or not text.strip():
        raise InputValidationError("Please enter a paragraph or passage before analyzing your vocabulary.")
    if max_length is None:
        load_environment()
        try:
            max_length = int(os.getenv("MAX_INPUT_CHARACTERS", "5000"))
        except ValueError:
            raise InputValidationError("MAX_INPUT_CHARACTERS must be a positive integer.") from None
    if isinstance(max_length, bool) or not isinstance(max_length, int) or max_length < 1:
        raise InputValidationError("MAX_INPUT_CHARACTERS must be a positive integer.")
    if len(text) > max_length:
        raise InputValidationError(f"Please shorten your passage to {max_length:,} characters or fewer.")
    if not re.search(r"[A-Za-z]{2,}", text):
        raise InputValidationError("Please enter meaningful English text containing words.")
    clean_text = " ".join(text.split())
    return PreparedText(text, clean_text, count_words(clean_text), len(clean_text))
