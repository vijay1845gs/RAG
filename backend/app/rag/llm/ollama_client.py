"""
Ollama Client Module for Local LLM Inference

This module provides functionality to interact with a local Ollama server for
running LLM inference with models like Qwen3. It handles connection management,
error handling, and provides a clean interface for generating responses from
local models.

Author: RAG System
Version: 1.0.0
"""

import logging
import requests
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Base exception for Ollama client errors."""

    pass


class OllamaConnectionError(OllamaError):
    """Raised when connection to Ollama server fails."""

    pass


class OllamaTimeoutError(OllamaError):
    """Raised when Ollama request times out."""

    pass


class OllamaModelError(OllamaError):
    """Raised when model-related operations fail."""

    pass


class OllamaGenerationError(OllamaError):
    """Raised when text generation fails."""

    pass


class InvalidInputError(OllamaError):
    """Raised when input parameters are invalid."""

    pass


class OllamaClient:
    """
    A production-grade Ollama client for local LLM inference.

    This class encapsulates Ollama functionality, handling connection management,
    request/response processing, and error handling. It provides clean interfaces
    for generating text using local LLM models.

    Attributes:
        base_url (str): Base URL of the Ollama server.
        model_name (str): Name of the model to use for inference.
        timeout (int): Request timeout in seconds.
        logger (logging.Logger): Logger instance for this class.

    Example:
        >>> client = OllamaClient(model_name="qwen3:8b")
        >>> response = client.generate("What is artificial intelligence?")
        >>> print(response)
    """

    # Default configuration
    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL_NAME = "qwen3:8b"
    DEFAULT_TIMEOUT = 120  # seconds
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_TOP_P = 0.9
    DEFAULT_TOP_K = 40

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model_name: str = DEFAULT_MODEL_NAME,
        timeout: int = DEFAULT_TIMEOUT,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = DEFAULT_TOP_P,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        """
        Initialize the Ollama client.

        Args:
            base_url (str): Base URL of Ollama server. Defaults to localhost:11434.
            model_name (str): Model name (e.g., "qwen3:8b"). Defaults to "qwen3:8b".
            timeout (int): Request timeout in seconds. Defaults to 120.
            temperature (float): Sampling temperature (0-1). Defaults to 0.7.
            top_p (float): Top-p sampling parameter (0-1). Defaults to 0.9.
            top_k (int): Top-k sampling parameter. Defaults to 40.

        Raises:
            InvalidInputError: If configuration is invalid.
            OllamaConnectionError: If unable to connect to Ollama server.

        Example:
            >>> client = OllamaClient(
            ...     base_url="http://localhost:11434",
            ...     model_name="qwen3:8b",
            ...     timeout=120
            ... )
        """
        self.logger = logger

        try:
            self._validate_config(
                base_url, model_name, timeout, temperature, top_p, top_k
            )

            self.base_url = base_url.rstrip("/")
            self.model_name = model_name
            self.timeout = timeout
            self.temperature = temperature
            self.top_p = top_p
            self.top_k = top_k

            self.logger.info(f"Ollama client initialized for model: {self.model_name}")

            # Test connection to Ollama server
            self._test_connection()

        except (InvalidInputError, OllamaConnectionError):
            raise

        except Exception as e:
            error_msg = (
                f"Error initializing Ollama client: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise OllamaError(error_msg) from e

    @staticmethod
    def _validate_config(
        base_url: str,
        model_name: str,
        timeout: int,
        temperature: float,
        top_p: float,
        top_k: int,
    ) -> None:
        """
        Validate client configuration parameters.

        Args:
            base_url (str): Server base URL.
            model_name (str): Model name.
            timeout (int): Request timeout.
            temperature (float): Temperature parameter.
            top_p (float): Top-p parameter.
            top_k (int): Top-k parameter.

        Raises:
            InvalidInputError: If any parameter is invalid.
        """
        if not base_url or not isinstance(base_url, str):
            raise InvalidInputError(
                f"base_url must be a non-empty string, got {type(base_url).__name__}"
            )

        if not model_name or not isinstance(model_name, str):
            raise InvalidInputError(
                f"model_name must be a non-empty string, got {type(model_name).__name__}"
            )

        if not isinstance(timeout, int) or timeout <= 0:
            raise InvalidInputError(f"timeout must be a positive integer, got {timeout}")

        if not isinstance(temperature, (int, float)) or not (0 <= temperature <= 1):
            raise InvalidInputError(
                f"temperature must be between 0 and 1, got {temperature}"
            )

        if not isinstance(top_p, (int, float)) or not (0 <= top_p <= 1):
            raise InvalidInputError(f"top_p must be between 0 and 1, got {top_p}")

        if not isinstance(top_k, int) or top_k < 0:
            raise InvalidInputError(f"top_k must be a non-negative integer, got {top_k}")

    def _test_connection(self) -> None:
        """
        Test connection to Ollama server.

        Raises:
            OllamaConnectionError: If connection fails.
        """
        try:
            self.logger.info(f"Testing connection to Ollama at {self.base_url}")

            response = requests.get(
                urljoin(self.base_url, "/api/tags"),
                timeout=10,
            )

            if response.status_code != 200:
                raise OllamaConnectionError(
                    f"Ollama server returned status {response.status_code}"
                )

            self.logger.info("Successfully connected to Ollama server")

        except requests.ConnectionError as e:
            error_msg = f"Failed to connect to Ollama at {self.base_url}: {str(e)}"
            self.logger.error(error_msg)
            raise OllamaConnectionError(error_msg) from e

        except requests.Timeout as e:
            error_msg = f"Connection to Ollama timed out: {str(e)}"
            self.logger.error(error_msg)
            raise OllamaTimeoutError(error_msg) from e

        except Exception as e:
            error_msg = (
                f"Error testing Ollama connection: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise OllamaConnectionError(error_msg) from e

    def _validate_prompt(self, prompt: str) -> None:
        """
        Validate prompt input.

        Args:
            prompt (str): Prompt text to validate.

        Raises:
            InvalidInputError: If prompt is invalid.
        """
        if not prompt or not isinstance(prompt, str):
            raise InvalidInputError(
                f"Prompt must be a non-empty string, got {type(prompt).__name__}"
            )

        if not prompt.strip():
            raise InvalidInputError("Prompt cannot be empty or whitespace-only")

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        stream: bool = False,
    ) -> str:
        """
        Generate text using the Ollama model.

        Sends a prompt to the local Ollama server and returns the generated
        response. Supports custom parameters and streaming mode.

        Args:
            prompt (str): The prompt to generate from.
            system (Optional[str]): System prompt/context. If None, not included.
            temperature (Optional[float]): Sampling temperature (0-1).
                If None, uses default.
            top_p (Optional[float]): Top-p sampling (0-1).
                If None, uses default.
            top_k (Optional[int]): Top-k sampling.
                If None, uses default.
            stream (bool): If True, streams response (not yet implemented).
                Defaults to False.

        Returns:
            str: The generated response text.

        Raises:
            InvalidInputError: If prompt is invalid.
            OllamaConnectionError: If connection fails.
            OllamaTimeoutError: If request times out.
            OllamaGenerationError: If generation fails.

        Example:
            >>> client = OllamaClient()
            >>> response = client.generate("What is machine learning?")
            >>> print(response)
        """
        try:
            self._validate_prompt(prompt)

            # Use provided parameters or defaults
            temp = temperature if temperature is not None else self.temperature
            p = top_p if top_p is not None else self.top_p
            k = top_k if top_k is not None else self.top_k

            self.logger.info(f"Generating response for prompt: {prompt[:100]}...")

            # Build request payload
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,  # Currently not supporting streaming
                "options": {
                    "temperature": temp,
                    "top_p": p,
                    "top_k": k,
                },
            }

            # Add system prompt if provided
            if system:
                payload["system"] = system

            # Send request to Ollama
            response = requests.post(
                urljoin(self.base_url, "/api/generate"),
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code != 200:
                error_msg = f"Ollama API returned status {response.status_code}: {response.text}"
                self.logger.error(error_msg)
                raise OllamaGenerationError(error_msg)

            # Parse response
            result = response.json()
            generated_text = result.get("response", "")

            if not generated_text:
                raise OllamaGenerationError("Empty response from Ollama")

            self.logger.debug(f"Generated {len(generated_text)} characters")

            return generated_text

        except InvalidInputError:
            raise

        except requests.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            self.logger.error(error_msg)
            raise OllamaConnectionError(error_msg) from e

        except requests.Timeout as e:
            error_msg = f"Request timeout: {str(e)}"
            self.logger.error(error_msg)
            raise OllamaTimeoutError(error_msg) from e

        except (OllamaGenerationError, OllamaConnectionError, OllamaTimeoutError):
            raise

        except Exception as e:
            error_msg = (
                f"Error generating response: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise OllamaGenerationError(error_msg) from e

    def generate_with_context(
        self,
        prompt: str,
        context: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Generate text using a prompt with additional context.

        Combines context with the prompt for more informed generation.
        Useful for RAG systems where context is retrieved separately.

        Args:
            prompt (str): The user query/prompt.
            context (str): Additional context to inform generation.
            system (Optional[str]): System prompt. If None, uses RAG default.
            temperature (Optional[float]): Sampling temperature.

        Returns:
            str: The generated response text.

        Raises:
            InvalidInputError: If prompt or context is invalid.
            OllamaGenerationError: If generation fails.

        Example:
            >>> client = OllamaClient()
            >>> context = "AI is artificial intelligence..."
            >>> response = client.generate_with_context(
            ...     prompt="What is AI?",
            ...     context=context
            ... )
        """
        try:
            self._validate_prompt(prompt)

            if not context or not isinstance(context, str):
                raise InvalidInputError("Context must be a non-empty string")

            # Build combined prompt
            combined_prompt = f"Context: {context}\n\nQuestion: {prompt}\n\nAnswer:"

            # Use provided system prompt or default
            default_system = (
                system
                or "You are a helpful AI assistant that answers questions based on provided context. "
                "Be concise and accurate."
            )

            response = self.generate(
                prompt=combined_prompt,
                system=default_system,
                temperature=temperature,
            )

            return response

        except InvalidInputError:
            raise

        except Exception as e:
            error_msg = (
                f"Error generating with context: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise OllamaGenerationError(error_msg) from e

    def list_available_models(self) -> List[str]:
        """
        List all available models on the Ollama server.

        Returns a list of model names that can be used for inference.

        Returns:
            List[str]: List of available model names.

        Raises:
            OllamaConnectionError: If connection fails.

        Example:
            >>> client = OllamaClient()
            >>> models = client.list_available_models()
            >>> print(f"Available models: {models}")
        """
        try:
            self.logger.info("Fetching available models from Ollama")

            response = requests.get(
                urljoin(self.base_url, "/api/tags"),
                timeout=self.timeout,
            )

            if response.status_code != 200:
                raise OllamaConnectionError(
                    f"Failed to fetch models: status {response.status_code}"
                )

            data = response.json()
            models = [model["name"] for model in data.get("models", [])]

            self.logger.info(f"Found {len(models)} available models")
            return models

        except requests.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            self.logger.error(error_msg)
            raise OllamaConnectionError(error_msg) from e

        except Exception as e:
            error_msg = (
                f"Error listing models: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise OllamaConnectionError(error_msg) from e

    def check_model_availability(self, model_name: Optional[str] = None) -> bool:
        """
        Check if a model is available on the Ollama server.

        Args:
            model_name (Optional[str]): Model name to check.
                If None, checks the configured model.

        Returns:
            bool: True if model is available, False otherwise.

        Example:
            >>> client = OllamaClient()
            >>> if client.check_model_availability():
            ...     response = client.generate("Hello!")
        """
        try:
            check_model = model_name or self.model_name
            available_models = self.list_available_models()

            return check_model in available_models

        except OllamaConnectionError:
            self.logger.warning("Could not verify model availability")
            return False

    def set_model(self, model_name: str) -> None:
        """
        Change the active model.

        Args:
            model_name (str): Name of the model to use.

        Raises:
            InvalidInputError: If model name is invalid.

        Example:
            >>> client = OllamaClient()
            >>> client.set_model("llama2:7b")
        """
        if not model_name or not isinstance(model_name, str):
            raise InvalidInputError("Model name must be a non-empty string")

        self.model_name = model_name
        self.logger.info(f"Active model changed to: {model_name}")

    def get_client_info(self) -> Dict[str, Any]:
        """
        Get information about the current client configuration.

        Returns:
            Dict[str, Any]: Dictionary with keys:
                - base_url: Ollama server URL
                - model_name: Current model
                - timeout: Request timeout
                - temperature: Temperature setting
                - top_p: Top-p setting
                - top_k: Top-k setting

        Example:
            >>> client = OllamaClient()
            >>> info = client.get_client_info()
            >>> print(f"Using model: {info['model_name']}")
        """
        return {
            "base_url": self.base_url,
            "model_name": self.model_name,
            "timeout": self.timeout,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }

    def __repr__(self) -> str:
        """Return string representation of the OllamaClient instance."""
        return (
            f"OllamaClient(base_url='{self.base_url}', model_name='{self.model_name}')"
        )

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"Ollama Client using {self.model_name} at {self.base_url}"


def generate_text(
    prompt: str,
    model_name: str = OllamaClient.DEFAULT_MODEL_NAME,
    base_url: str = OllamaClient.DEFAULT_BASE_URL,
) -> str:
    """
    Convenience function to generate text with a single call.

    Creates a client and generates text in one operation. Useful for
    simple use cases that don't need client reuse.

    Args:
        prompt (str): The prompt to generate from.
        model_name (str): Model to use. Defaults to qwen3:8b.
        base_url (str): Ollama server URL. Defaults to localhost:11434.

    Returns:
        str: Generated response text.

    Raises:
        InvalidInputError: If prompt is invalid.
        OllamaGenerationError: If generation fails.

    Example:
        >>> response = generate_text("What is AI?")
        >>> print(response)
    """
    client = OllamaClient(model_name=model_name, base_url=base_url)
    return client.generate(prompt)


def generate_with_rag_context(
    prompt: str,
    context: str,
    model_name: str = OllamaClient.DEFAULT_MODEL_NAME,
    base_url: str = OllamaClient.DEFAULT_BASE_URL,
) -> str:
    """
    Convenience function to generate text with context.

    Args:
        prompt (str): The user query.
        context (str): Retrieved context for informed generation.
        model_name (str): Model to use.
        base_url (str): Ollama server URL.

    Returns:
        str: Generated response text.

    Example:
        >>> context = "AI is artificial intelligence..."
        >>> response = generate_with_rag_context("What is AI?", context)
    """
    client = OllamaClient(model_name=model_name, base_url=base_url)
    return client.generate_with_context(prompt, context)
