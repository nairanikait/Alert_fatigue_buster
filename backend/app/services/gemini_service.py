"""
Official Google Gemini Service for Alert Buster.
Uses the official google-genai SDK to interface with Gemini models.
Reads API key strictly from the GEMINI_API_KEY environment variable.
Never hardcodes secrets. Never exposes the key to client code.
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List
import anyio

from app.core.config import settings

logger = logging.getLogger("alert_buster.services.gemini")

# Import the official SDK
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError, ClientError, ServerError
    HAS_GEMINI_SDK = True
except ImportError:
    HAS_GEMINI_SDK = False
    genai = None
    types = None
    APIError = Exception
    ClientError = Exception
    ServerError = Exception


class GeminiNotConfiguredError(Exception):
    """Raised when GEMINI_API_KEY is missing or empty in environment."""
    pass


class GeminiAuthenticationError(Exception):
    """Raised when GEMINI_API_KEY is rejected (401/403) by Google Gemini API."""
    pass


class GeminiRateLimitError(Exception):
    """Raised when Gemini quota or rate limits are exceeded (429)."""
    pass


class GeminiServiceError(Exception):
    """General wrapper for Gemini API call failures."""
    pass


class GeminiService:
    """
    Singleton service for interacting with Google Gemini models via the official SDK.
    API keys are strictly sourced from the GEMINI_API_KEY environment variable.
    """

    DEFAULT_MODEL = "gemini-3.6-flash"
    FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"]

    def __init__(self):
        self._client = None
        self._cached_key = None

    def get_api_key(self) -> Optional[str]:
        """
        Retrieves the Gemini API key strictly from the environment or settings.
        Never hardcodes keys.
        """
        key = os.environ.get("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
        if key and str(key).strip():
            return str(key).strip()
        return None

    def is_configured(self) -> bool:
        """Returns True if a non-empty GEMINI_API_KEY is available."""
        return self.get_api_key() is not None

    def get_client(self, override_key: Optional[str] = None) -> Any:
        """
        Initializes and returns the official genai.Client instance.
        Raises GeminiNotConfiguredError if no key is present.
        """
        if not HAS_GEMINI_SDK:
            raise GeminiServiceError(
                "The official 'google-genai' SDK is not installed in the environment. "
                "Install it using: pip install google-genai"
            )

        if override_key is not None:
            api_key = override_key.strip() if override_key else None
        else:
            api_key = self.get_api_key()

        if not api_key:
            raise GeminiNotConfiguredError(
                "GEMINI_API_KEY environment variable is not set. "
                "Please configure GEMINI_API_KEY in your .env file or environment variables."
            )

        # Cache or recreate client if key changes
        if self._client is None or self._cached_key != api_key:
            self._client = genai.Client(api_key=api_key)
            self._cached_key = api_key

        return self._client

    def generate_chat_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        override_key: Optional[str] = None,
    ) -> str:
        """
        Synchronously generates a chat response using Google's official SDK client.chats.
        Supports system_instruction and conversation history.
        """
        client = self.get_client(override_key=override_key)
        target_model = model or self.DEFAULT_MODEL

        # Configure system instruction and temperature
        config_kwargs: Dict[str, Any] = {
            "temperature": temperature,
        }
        if system_instruction and system_instruction.strip():
            config_kwargs["system_instruction"] = system_instruction.strip()

        config = types.GenerateContentConfig(**config_kwargs) if types else None

        # Build history formatted for Gemini SDK
        chat_history = []
        if history and types:
            for item in history:
                role = item.get("role", "user")
                # Map assistant role to model for Gemini
                gemini_role = "model" if role in ("assistant", "model", "system") else "user"
                content_text = item.get("content", "")
                if content_text:
                    chat_history.append(
                        types.Content(
                            role=gemini_role,
                            parts=[types.Part.from_text(text=content_text)]
                        )
                    )

        models_to_try = [target_model]
        for m in self.FALLBACK_MODELS:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error = None
        for current_model in models_to_try:
            try:
                logger.info("Calling Gemini API via official SDK using model: %s", current_model)
                chat = client.chats.create(
                    model=current_model,
                    config=config,
                    history=chat_history if chat_history else None,
                )
                response = chat.send_message(prompt)
                if response and response.text:
                    return response.text.strip()
                return "No response text received from Gemini API."

            except ClientError as e:
                err_str = str(e)
                code = getattr(e, "code", None)

                # Check for Authentication errors (401, 403, invalid key)
                if code in (401, 403) or "API_KEY_INVALID" in err_str or "unauthorized" in err_str.lower():
                    logger.error("Gemini API authentication failed: %s", e)
                    raise GeminiAuthenticationError(
                        f"Invalid or unauthorized GEMINI_API_KEY: {err_str}"
                    ) from e

                # Check for Rate Limit / Quota errors (429)
                if code == 429 or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                    logger.warning("Gemini API rate limit / quota exceeded: %s", e)
                    raise GeminiRateLimitError(
                        "Gemini API rate limit or quota exceeded. Please retry shortly."
                    ) from e

                # If model is not found / deprecated (404), try fallback model
                if code == 404 or "not found" in err_str.lower() or "no longer available" in err_str.lower():
                    logger.warning("Model %s unavailable (404), trying fallback: %s", current_model, e)
                    last_error = e
                    continue

                logger.error("Gemini ClientError on model %s: %s", current_model, e)
                raise GeminiServiceError(f"Gemini API client error ({code}): {err_str}") from e

            except ServerError as e:
                logger.warning("Gemini ServerError on model %s: %s", current_model, e)
                last_error = e
                continue

            except Exception as e:
                logger.error("Unexpected error calling Gemini API on model %s: %s", current_model, e)
                raise GeminiServiceError(f"Failed to communicate with Gemini API: {str(e)}") from e

        if last_error:
            raise GeminiServiceError(f"All Gemini models failed. Last error: {str(last_error)}")
        raise GeminiServiceError("Failed to generate content from Gemini API.")

    async def async_generate_chat_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        override_key: Optional[str] = None,
    ) -> str:
        """
        Asynchronously generates a chat response without blocking the FastAPI event loop.
        """
        return await anyio.to_thread.run_sync(
            self.generate_chat_response,
            prompt,
            system_instruction,
            history,
            model,
            temperature,
            override_key,
        )

    def test_connection(self, override_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Performs a lightweight health check against the Gemini API using the official SDK.
        Returns detailed diagnostics (latency, model, status, response preview).
        """
        start_time = time.time()
        try:
            reply = self.generate_chat_response(
                prompt="Respond in 10 words or less confirming that Gemini API integration is online.",
                model=self.DEFAULT_MODEL,
                override_key=override_key,
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "success": True,
                "configured": True,
                "model": self.DEFAULT_MODEL,
                "latency_ms": elapsed_ms,
                "response": reply,
                "sdk": "google-genai",
            }
        except GeminiNotConfiguredError as e:
            return {
                "success": False,
                "configured": False,
                "error_type": "NOT_CONFIGURED",
                "message": str(e),
                "hint": "Set GEMINI_API_KEY in .env file or as an environment variable.",
            }
        except GeminiAuthenticationError as e:
            return {
                "success": False,
                "configured": True,
                "error_type": "AUTHENTICATION_FAILED",
                "message": str(e),
                "hint": "Verify that your GEMINI_API_KEY is active and has permissions for Google AI Studio / Gemini API.",
            }
        except GeminiRateLimitError as e:
            return {
                "success": False,
                "configured": True,
                "error_type": "RATE_LIMIT_EXCEEDED",
                "message": str(e),
                "hint": "Check your Gemini API quota or wait a moment before retrying.",
            }
        except Exception as e:
            return {
                "success": False,
                "configured": self.is_configured(),
                "error_type": type(e).__name__,
                "message": str(e),
            }


# Global singleton service
gemini_service = GeminiService()
