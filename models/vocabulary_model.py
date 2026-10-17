"""Provider-independent output models; these do not generate vocabulary."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VocabularyEntry(BaseModel):
    """One word and its explanation in the context of the submitted passage."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    word: str = Field(min_length=1)
    definition: str = Field(min_length=1)
    original_context: str = Field(min_length=1)
    example_sentence: str = Field(min_length=1)
    difficulty_level: Literal["beginner", "intermediate", "advanced"]


class VocabularyAnalysisResult(BaseModel):
    """Complete future analysis, including the source passage and vocabulary."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    original_text: str = Field(min_length=1)
    entries: list[VocabularyEntry] = Field(default_factory=list)
