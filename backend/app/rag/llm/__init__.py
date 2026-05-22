"""
LLM Module

This package provides LLM inference functionality for RAG systems, including
local inference with Ollama and support for models like Qwen3.
"""

from app.rag.llm.ollama_client import (
    OllamaClient,
    OllamaError,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelError,
    OllamaGenerationError,
    InvalidInputError,
    generate_text,
    generate_with_rag_context,
)

__all__ = [
    "OllamaClient",
    "OllamaError",
    "OllamaConnectionError",
    "OllamaTimeoutError",
    "OllamaModelError",
    "OllamaGenerationError",
    "InvalidInputError",
    "generate_text",
    "generate_with_rag_context",
]
