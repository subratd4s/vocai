"""Provider-independent output models; these do not generate vocabulary."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DifficultyLevel(str, Enum):
    """Shared reader levels; accept legacy lowercase Phase 1 values."""

    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            return next((level for level in cls if level.value.lower() == value.lower()), None)
        return None


class VocabularyEntry(BaseModel):
    """One word and its explanation in the context of the submitted passage."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    word: str = Field(min_length=1)
    definition: str = Field(min_length=1)
    original_context: str = Field(min_length=1)
    example_sentence: str = Field(min_length=1)
    difficulty_level: DifficultyLevel


class VocabularyAnalysisResult(BaseModel):
    """Complete vocabulary output, including the source passage and entries."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    original_text: str = Field(min_length=1)
    entries: list[VocabularyEntry] = Field(default_factory=list)


class DefinitionBatch(BaseModel):
    """One structured generation request for all selected vocabulary."""

    model_config = ConfigDict(extra="forbid")
    entries: list[VocabularyEntry]


class IdentifiedWord(BaseModel):
    """Identification metadata passed to the separate definition generator."""

    model_config = ConfigDict(extra="forbid")

    word: str = Field(min_length=1)
    difficulty_level: DifficultyLevel
    original_context: str = Field(min_length=1)


class WordSelection(BaseModel):
    """Minimal provider response; passage statistics are computed locally."""

    model_config = ConfigDict(extra="forbid")

    identified_words: list[IdentifiedWord]


class IdentificationResult(WordSelection):
    """Validated selections with authoritative input metadata."""

    original_text: str = Field(min_length=1)
    selected_difficulty: DifficultyLevel
    total_words_analyzed: int = Field(ge=0)
