"""
FastAPI Chat Routes for RAG Question Answering

This module provides RESTful endpoints for:
- Asking questions to the RAG system
- Retrieving chat history
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.schemas.chat_schema import (
    ChatRequest,
    ChatResponse,
    ChatErrorResponse,
)
from app.services.chat_service import (
    ChatService,
    ChatServiceError,
    ChatValidationError,
    ChatRetrievalError,
    ChatGenerationError,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "model": ChatErrorResponse,
            "description": "Invalid chat request parameters",
        },
        500: {
            "model": ChatErrorResponse,
            "description": "RAG pipeline or LLM failure",
        },
    },
    summary="Ask a question to the RAG system",
    description=(
        "Send a question to the RAG system for retrieval-augmented generation. "
        "The system will retrieve relevant document chunks and generate an answer."
    ),
)
async def ask_question(request: ChatRequest) -> ChatResponse:
    """
    Process a chat query through the RAG pipeline.

    Orchestrates retrieval, prompt building, generation, and source formatting.

    **Request Body:**
    - `question`: User question (required, 3-4000 chars)
    - `collection_id`: Optional target collection for scoped retrieval
    - `top_k`: Optional number of chunks to retrieve (1-20)

    **Response:**
    Returns `ChatResponse` with:
    - `answer`: Generated answer text
    - `sources`: List of source citations
    - `retrieved_chunks`: Number of chunks used
    - `response_time`: Generation latency in seconds

    **Error Handling:**
    - **400 Bad Request**: Invalid question or parameters
    - **500 Internal Server Error**: Retrieval or generation failure
    """
    try:
        chat_service = ChatService()
        response = chat_service.ask_question(
            question=request.question,
            top_k=request.top_k,
            collection_id=request.collection_id,
            temperature=request.temperature,
            rag_mode=request.rag_mode,
            response_style=request.response_style,
            show_sources=request.show_sources,
        )
        return response

    except ChatValidationError as exc:
        logger.warning("Chat validation failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ChatErrorResponse(error="Validation error", details=str(exc)).model_dump(),
        ) from exc

    except (ChatRetrievalError, ChatGenerationError) as exc:
        logger.error("Chat processing failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ChatErrorResponse(
                error="Chat processing failed", details="Unable to process chat request"
            ).model_dump(),
        ) from exc

    except ChatServiceError as exc:
        logger.error("Chat service error: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ChatErrorResponse(
                error="Service error", details="An error occurred processing your request"
            ).model_dump(),
        ) from exc

    except Exception as exc:
        logger.exception("Unexpected error in chat endpoint")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ChatErrorResponse(
                error="Unexpected error", details="An unexpected error occurred"
            ).model_dump(),
        ) from exc