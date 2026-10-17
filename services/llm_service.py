"""OpenAI adapter with structured parsing and sanitized, provider-neutral errors."""

import os
from typing import Protocol, TypeVar

from openai import (
    APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError,
    OpenAI, RateLimitError,
)
from pydantic import BaseModel, ValidationError

from utils.config import load_environment

OutputT = TypeVar("OutputT", bound=BaseModel)


class LLMServiceError(RuntimeError):
    """Only safe application-authored messages cross the service boundary."""


class StructuredOutputError(LLMServiceError):
    """Malformed output that the workflow may request once more with feedback."""


class StructuredLLM(Protocol):
    """Provider boundary usable by agents and later LangGraph nodes."""

    def request_structured(self, system_prompt: str, user_data: str, schema: type[OutputT]) -> OutputT: ...


class LLMService:
    """Create a short-lived client only when an explicit analysis is requested."""

    def request_structured(self, system_prompt: str, user_data: str, schema: type[OutputT]) -> OutputT:
        load_environment()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or api_key == "your_api_key_here":
            raise LLMServiceError("Please configure OPENAI_API_KEY in your .env file to analyze vocabulary.")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        if not model:
            raise LLMServiceError("Please configure OPENAI_MODEL in your .env file.")
        try:
            with OpenAI(api_key=api_key, timeout=30.0, max_retries=0) as client:
                response = client.responses.parse(
                    model=model,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_data},
                    ],
                    text_format=schema,
                    store=False,
                )
            if response.status != "completed" or response.output_parsed is None:
                raise LLMServiceError("The AI service did not return a complete structured response. Please try again.")
            return schema.model_validate(response.output_parsed.model_dump())
        except AuthenticationError:
            raise LLMServiceError("The AI service rejected the API key. Please check your OpenAI credentials.") from None
        except APITimeoutError:
            raise LLMServiceError("The AI request timed out. Please try again.") from None
        except APIConnectionError:
            raise LLMServiceError("Unable to connect to the AI service. Please check your internet connection and try again.") from None
        except RateLimitError:
            raise LLMServiceError("The AI service rate limit or quota was exceeded. Please check your quota or try again later.") from None
        except APIStatusError:
            raise LLMServiceError("The AI service could not complete the request. Please check model access or try again later.") from None
        except (ValidationError, ValueError, TypeError):
            raise StructuredOutputError("The AI service returned an invalid structured response. Check required fields and nonempty values.") from None
        except LLMServiceError:
            raise
        except Exception:
            raise LLMServiceError("An unexpected AI service error occurred. Please try again later.") from None
