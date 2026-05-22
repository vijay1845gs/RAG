"""
Pipelines Module

This package provides orchestration and workflow functionality for RAG systems,
including the central retrieval-augmented generation pipeline that coordinates
all components.
"""

from app.rag.pipelines.retrieval_pipeline import (
    RetrievalPipeline,
    RAGResponse,
    PipelineError,
    ComponentError,
    QueryProcessingError,
    RetrievalError,
    GenerationError,
    InvalidInputError,
    create_rag_pipeline,
)

__all__ = [
    "RetrievalPipeline",
    "RAGResponse",
    "PipelineError",
    "ComponentError",
    "QueryProcessingError",
    "RetrievalError",
    "GenerationError",
    "InvalidInputError",
    "create_rag_pipeline",
]
