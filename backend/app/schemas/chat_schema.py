"""
Pydantic schemas for AI chat endpoints.

These models are designed for FastAPI request validation, OpenAPI generation,
and JSON-safe serialization in the RAG backend.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    """
    Request body for a RAG chat query.

    `question` is trimmed before validation. Empty or too-short questions are
    rejected before they reach retrieval or LLM generation.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "question": "What is NLP?",
                    "collection_id": "cia_notes",
                    "top_k": 3,
                }
            ]
        },
    )

    question: str = Field(
        ...,
        min_length=3,
        max_length=4000,
        description="User question to answer using the RAG pipeline.",
        examples=["What are intelligent systems in healthcare?"],
    )
    collection_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional vector collection identifier to query.",
        examples=["cia_notes"],
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Optional number of relevant chunks to retrieve.",
        examples=[3],
    )
    # ─── Settings-injected fields (optional, sent by the frontend) ───────
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="LLM temperature override from user settings.",
    )
    rag_mode: Optional[str] = Field(
        default=None,
        description="RAG mode: 'precise' | 'balanced' | 'creative'.",
    )
    response_style: Optional[str] = Field(
        default=None,
        description="Response style: professional | concise | beginner_friendly | research | technical.",
    )
    show_sources: Optional[bool] = Field(
        default=None,
        description="Whether to include source citations in the response.",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID for per-user settings lookup.",
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        """Normalize and validate the user question."""
        question = value.strip()
        if not question:
            raise ValueError("question must not be empty")
        if len(question) < 3:
            raise ValueError("question must be at least 3 characters long")
        return question

    @field_validator("collection_id")
    @classmethod
    def validate_collection_id(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional collection identifiers."""
        if value is None:
            return None

        collection_id = value.strip()
        if not collection_id:
            raise ValueError("collection_id must not be empty when provided")
        return collection_id


class SourceResponse(BaseModel):
    """Source citation returned with a generated answer."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "source_file": "cia_notes.pdf",
                    "page_number": 16,
                    "chunk_id": "chunk-0032",
                    "relevance_score": 0.8734,
                }
            ]
        }
    )

    source_file: str = Field(
        ...,
        min_length=1,
        description="Source document or file name used for the answer.",
        examples=["cia_notes.pdf"],
    )
    page_number: Optional[int] = Field(
        default=None,
        ge=0,
        description="Zero-based or source-native page number when available.",
        examples=[16],
    )
    chunk_id: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Identifier of the retrieved chunk when available.",
        examples=["chunk-0032"],
    )
    relevance_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Similarity or relevance score returned by retrieval.",
        examples=[0.8734],
    )


class ChatResponse(BaseModel):
    """Successful AI chat response."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "answer": "NLP helps computers understand and generate human language.",
                    "sources": [
                        {
                            "source_file": "cia_notes.pdf",
                            "page_number": 16,
                            "chunk_id": "chunk-0032",
                            "relevance_score": 0.8734,
                        }
                    ],
                    "retrieved_chunks": 3,
                    "response_time": 2.481,
                }
            ]
        }
    )

    answer: str = Field(
        ...,
        min_length=1,
        description="Generated answer from the RAG pipeline.",
    )
    sources: List[SourceResponse] = Field(
        default_factory=list,
        description="Source citations used to ground the answer.",
    )
    retrieved_chunks: int = Field(
        ...,
        ge=0,
        description="Number of chunks retrieved for the answer.",
        examples=[3],
    )
    response_time: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Total response time in seconds when measured.",
        examples=[2.481],
    )


class ChatErrorResponse(BaseModel):
    """Error response for chat endpoint failures."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "error": "RAG pipeline failed",
                    "details": "Ollama request timed out after 120 seconds.",
                }
            ]
        }
    )

    error: str = Field(
        ...,
        min_length=1,
        description="Short, client-safe error message.",
        examples=["RAG pipeline failed"],
    )
    details: Optional[str] = Field(
        default=None,
        description="Optional diagnostic details suitable for API clients.",
        examples=["Ollama request timed out after 120 seconds."],
    )
