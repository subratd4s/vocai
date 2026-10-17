"""Small text utilities used by the interface."""


def count_words(text: str) -> int:
    """Count whitespace-separated tokens; punctuation stays with its token."""
    return len(text.split())
