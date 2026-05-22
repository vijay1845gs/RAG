"""
Standalone integration test for local Ollama + qwen3 inference.

This script verifies that the project OllamaClient can connect to a local
Ollama server and generate text with qwen3:8b. It does not run retrieval,
ChromaDB, FastAPI, or any RAG orchestration.

Usage:
    python backend/test_ollama.py
"""

import logging
import sys
from importlib.util import find_spec
from pathlib import Path
from typing import Any


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


MODEL_NAME = "qwen3:8b"
PROMPT = "Explain Retrieval-Augmented Generation simply."
BASE_URL = "http://localhost:11434"
TIMEOUT_SECONDS = 180


def setup_paths() -> None:
    """Add backend directory to Python path for app.* imports."""
    backend_dir = Path(__file__).parent
    sys.path.insert(0, str(backend_dir))
    logger.debug("Added to sys.path: %s", backend_dir)


def print_separator(title: str = "", width: int = 80) -> None:
    """Print a formatted separator line."""
    if title:
        padding = max((width - len(title) - 2) // 2, 0)
        print("=" * padding + f" {title} " + "=" * (width - padding - len(title) - 2))
    else:
        print("=" * width)


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print()
    print_separator(title)


def safe_console_text(value: Any) -> str:
    """Return text that can be printed safely on the active Windows console."""
    text = str(value)
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


def validate_response(response: str) -> None:
    """Validate that Ollama returned usable generated text."""
    if not isinstance(response, str):
        raise ValueError(f"Response must be a string, got {type(response).__name__}.")

    if not response.strip():
        raise ValueError("Ollama returned an empty response.")


def validate_model_available(client: Any, model_name: str) -> None:
    """Validate that the requested model is available locally."""
    available_models = client.list_available_models()

    if model_name not in available_models:
        available_text = ", ".join(available_models) if available_models else "none"
        raise ValueError(
            f"Model '{model_name}' is not available in local Ollama. "
            f"Available models: {available_text}. "
            f"Install it with: ollama pull {model_name}"
        )


def run_ollama_test() -> bool:
    """
    Execute the Ollama inference integration test.

    Returns:
        bool: True when the test passes, False otherwise.
    """
    try:
        print_section("IMPORTING MODULES")
        logger.info("Importing OllamaClient...")

        from app.rag.llm import (
            OllamaClient,
            OllamaConnectionError,
            OllamaError,
            OllamaGenerationError,
            OllamaTimeoutError,
        )

        print("[OK] Successfully imported OllamaClient")
        if find_spec("ollama") is not None:
            print("[OK] ollama Python package is installed")
        else:
            print("[WARN] ollama Python package is not installed; using project HTTP client")
        logger.info("Imports completed successfully")

        print_section("CONNECTING TO OLLAMA")
        print(f"Ollama base URL: {BASE_URL}")
        print(f"Model name: {MODEL_NAME}")
        print(f"Timeout: {TIMEOUT_SECONDS} seconds")

        client = OllamaClient(
            base_url=BASE_URL,
            model_name=MODEL_NAME,
            timeout=TIMEOUT_SECONDS,
            temperature=0.2,
            top_p=0.9,
            top_k=40,
        )

        validate_model_available(client, MODEL_NAME)
        print("[OK] Ollama connection works")
        print("[OK] qwen3:8b is available locally")

        print_section("GENERATING RESPONSE")
        logger.info("Sending prompt to Ollama model %s", MODEL_NAME)
        response = client.generate(prompt=PROMPT)
        validate_response(response)

        response_length = len(response.strip())

        print(f"Model name: {MODEL_NAME}")
        print(f"Prompt used: {PROMPT}")
        print(f"Response length: {response_length} characters")

        print_section("GENERATED RESPONSE")
        print(safe_console_text(response.strip()))

        print_section("VALIDATION")
        print("[OK] Response is non-empty")
        print("[OK] Ollama connection works")
        print("[OK] qwen3 inference completed successfully")

        print_section("TEST RESULT")
        print("[OK] OLLAMA QWEN3 INFERENCE TEST PASSED")
        logger.info("Ollama integration test passed")
        return True

    except ImportError as exc:
        print_section("ERROR - IMPORT FAILED")
        print(f"[ERROR] Failed to import required module: {exc}")
        logger.error("Import failed", exc_info=True)
        return False

    except ValueError as exc:
        print_section("ERROR - VALIDATION FAILED")
        print(f"[ERROR] {exc}")
        logger.error("Validation failed: %s", exc)
        return False

    except OllamaTimeoutError as exc:
        print_section("ERROR - OLLAMA TIMEOUT")
        print(f"[ERROR] Ollama request timed out: {exc}")
        logger.error("Ollama timeout: %s", exc)
        return False

    except OllamaConnectionError as exc:
        print_section("ERROR - OLLAMA CONNECTION FAILED")
        print(f"[ERROR] Could not connect to local Ollama server: {exc}")
        print("[INFO] Start Ollama locally, then rerun: python backend/test_ollama.py")
        logger.error("Ollama connection failed: %s", exc)
        return False

    except OllamaGenerationError as exc:
        print_section("ERROR - GENERATION FAILED")
        print(f"[ERROR] Ollama generation failed: {exc}")
        logger.error("Ollama generation failed: %s", exc)
        return False

    except OllamaError as exc:
        print_section("ERROR - OLLAMA FAILED")
        print(f"[ERROR] Ollama error: {exc}")
        logger.error("Ollama failed: %s", exc)
        return False

    except Exception as exc:
        print_section("ERROR - UNEXPECTED FAILURE")
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        logger.error("Unexpected Ollama test failure", exc_info=True)
        return False


def main() -> int:
    """
    Main entry point.

    Returns:
        int: 0 for success, 1 for failure, 130 when interrupted.
    """
    print()
    print_separator()
    print(" OLLAMA QWEN3 INFERENCE INTEGRATION TEST")
    print_separator()

    setup_paths()

    try:
        success = run_ollama_test()

        print()
        print_separator()
        if success:
            print(" Test execution completed successfully")
            exit_code = 0
        else:
            print(" Test execution failed")
            exit_code = 1
        print_separator()
        print()

        return exit_code

    except KeyboardInterrupt:
        print()
        print_section("INTERRUPTED")
        print("[ERROR] Test interrupted by user")
        logger.warning("Test interrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(main())
