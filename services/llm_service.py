"""Gemini adapter with structured parsing and sanitized provider-neutral errors."""

import os
from typing import Protocol, TypeVar

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from utils.config import load_environment

OutputT = TypeVar("OutputT", bound=BaseModel)


class LLMServiceError(RuntimeError):
    """Only safe application-authored messages cross the service boundary."""


class StructuredOutputError(LLMServiceError):
    """Malformed output eligible for the workflow's bounded correction."""


class StructuredLLM(Protocol):
    """Provider boundary shared by all vocabulary agents."""

    def request_structured(self, system_prompt: str, user_data: str, schema: type[OutputT]) -> OutputT: ...


class LLMService:
    """Use a short-lived Gemini Developer API client on explicit analysis only."""

    def request_structured(self, system_prompt: str, user_data: str, schema: type[OutputT]) -> OutputT:
        load_environment()
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key or api_key == "your_api_key_here":
            raise LLMServiceError("Please configure GEMINI_API_KEY in your .env file to analyze vocabulary.")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        if not model:
            raise LLMServiceError("Please configure GEMINI_MODEL in your .env file.")
        try:
            with genai.Client(
                api_key=api_key, vertexai=False,
                http_options=types.HttpOptions(timeout=30_000, retry_options=types.HttpRetryOptions(attempts=1)),
            ) as client:
                response = client.models.generate_content(
                    model=model, contents=user_data,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json", response_json_schema=schema.model_json_schema(),
                    ),
                )
            if not response.candidates or response.candidates[0].finish_reason != types.FinishReason.STOP:
                raise LLMServiceError("The AI service did not return a complete structured response. Please try again.")
            if not response.text:
                raise StructuredOutputError("The AI service returned an empty structured response. Please try again.")
            # Validate the raw JSON even if the SDK populated parsed; never trust partial output.
            return schema.model_validate_json(response.text)
        except errors.APIError as error:
            if error.code in (401, 403) or (error.code == 400 and "API_KEY_INVALID" in str(error.details)):
                message = "The AI service rejected the API key or its permissions. Please check your Gemini credentials."
            elif error.code == 429:
                message = "The AI service rate limit or quota was exceeded. Please check your quota or try again later."
            elif error.code == 503:
                message = "The AI service is temporarily overloaded. Please try again later."
            elif error.code in (408, 504):
                message = "The AI request timed out. Please try again."
            else:
                message = "The AI service could not complete the request. Please check model access or try again later."
            raise LLMServiceError(message) from None
        except httpx.TimeoutException:
            raise LLMServiceError("The AI request timed out. Please try again.") from None
        except httpx.TransportError:
            raise LLMServiceError("Unable to connect to the AI service. Please check your internet connection and try again.") from None
        except (ValidationError, ValueError, TypeError):
            raise StructuredOutputError("The AI service returned an invalid structured response. Check required fields and nonempty values.") from None
        except LLMServiceError:
            raise
        except Exception:
            raise LLMServiceError("An unexpected AI service error occurred. Please try again later.") from None
