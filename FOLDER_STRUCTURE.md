RAG/
├── backend/
│   ├── __init__.py
│   ├── .env.example
│   │
│   ├── main.py
│   ├── requirements.txt
│   ├── pyproject.toml
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── documents.py
│   │   │   ├── collections.py
│   │   │   ├── chat.py
│   │   │   ├── search.py
│   │   │   └── health.py
│   │   │
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── auth_middleware.py
│   │   │   ├── error_handler.py
│   │   │   └── cors_handler.py
│   │   │
│   │   └── dependencies/
│   │       ├── __init__.py
│   │       ├── auth_deps.py
│   │       └── db_deps.py
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   │
│   │   ├── loaders/
│   │   │   ├── __init__.py
│   │   │   ├── pdf_loader.py
│   │   │   ├── docx_loader.py
│   │   │   └── base_loader.py
│   │   │
│   │   ├── chunking/
│   │   │   ├── __init__.py
│   │   │   ├── chunker_strategy.py
│   │   │   ├── semantic_chunker.py
│   │   │   └── recursive_chunker.py
│   │   │
│   │   ├── embeddings/
│   │   │   ├── __init__.py
│   │   │   ├── embedding_service.py
│   │   │   └── model_manager.py
│   │   │
│   │   ├── vectorstore/
│   │   │   ├── __init__.py
│   │   │   ├── chroma_store.py
│   │   │   ├── base_vectorstore.py
│   │   │   └── collection_manager.py
│   │   │
│   │   ├── retrievers/
│   │   │   ├── __init__.py
│   │   │   ├── semantic_retriever.py
│   │   │   ├── hybrid_retriever.py
│   │   │   └── base_retriever.py
│   │   │
│   │   ├── pipelines/
│   │   │   ├── __init__.py
│   │   │   ├── ingestion_pipeline.py
│   │   │   ├── qa_pipeline.py
│   │   │   └── citation_pipeline.py
│   │   │
│   │   ├── prompts/
│   │   │   ├── __init__.py
│   │   │   ├── qa_prompts.py
│   │   │   ├── system_prompts.py
│   │   │   └── prompt_templates.py
│   │   │
│   │   └── llm/
│   │       ├── __init__.py
│   │       ├── ollama_client.py
│   │       ├── llm_service.py
│   │       └── response_parser.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── document_service.py
│   │   ├── collection_service.py
│   │   ├── chat_service.py
│   │   ├── citation_service.py
│   │   ├── search_service.py
│   │   ├── upload_service.py
│   │   ├── cache_service.py
│   │   └── auth_service.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── session.py
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── document.py
│   │   │   ├── collection.py
│   │   │   ├── chat_message.py
│   │   │   ├── chat_session.py
│   │   │   └── base.py
│   │   │
│   │   └── migrations/
│   │       ├── __init__.py
│   │       ├── versions/
│   │       ├── env.py
│   │       └── script.py.mako
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user_schema.py
│   │   ├── document_schema.py
│   │   ├── collection_schema.py
│   │   ├── chat_schema.py
│   │   ├── search_schema.py
│   │   └── common_schema.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── file_utils.py
│   │   ├── validators.py
│   │   ├── logger.py
│   │   ├── decorators.py
│   │   └── constants.py
│   │
│   ├── uploads/
│   │   ├── temp/
│   │   └── processed/
│   │
│   ├── chroma_db/
│   │   └── (ChromaDB persistent storage)
│   │
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── jwt_handler.py
│   │   ├── password_utils.py
│   │   └── oauth_handler.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── database_config.py
│   │   └── logging_config.py
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   │
│   │   ├── unit/
│   │   │   ├── __init__.py
│   │   │   ├── test_loaders.py
│   │   │   ├── test_chunking.py
│   │   │   ├── test_embeddings.py
│   │   │   ├── test_retrievers.py
│   │   │   └── test_services.py
│   │   │
│   │   ├── integration/
│   │   │   ├── __init__.py
│   │   │   ├── test_ingestion_pipeline.py
│   │   │   ├── test_qa_pipeline.py
│   │   │   ├── test_api_routes.py
│   │   │   └── test_db_operations.py
│   │   │
│   │   └── fixtures/
│   │       ├── __init__.py
│   │       ├── sample_documents/
│   │       └── mock_data.py
│   │
│   └── logs/
│       └── app.log
│
├── frontend/
│   ├── .gitkeep
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── .env.example
│   │
│   ├── index.html
│   ├── public/
│   │   └── (static assets)
│   │
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── App.css
│   │   ├── vite-env.d.ts
│   │   │
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Chat.tsx
│   │   │   ├── Collections.tsx
│   │   │   ├── Search.tsx
│   │   │   ├── Documents.tsx
│   │   │   ├── Auth/
│   │   │   │   ├── Login.tsx
│   │   │   │   └── Register.tsx
│   │   │   └── NotFound.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── common/
│   │   │   │   ├── Header.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── Footer.tsx
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Modal.tsx
│   │   │   │   ├── Loading.tsx
│   │   │   │   └── ErrorBoundary.tsx
│   │   │   │
│   │   │   ├── chat/
│   │   │   │   ├── ChatWindow.tsx
│   │   │   │   ├── ChatMessage.tsx
│   │   │   │   ├── ChatInput.tsx
│   │   │   │   ├── MessageList.tsx
│   │   │   │   └── ChatHistory.tsx
│   │   │   │
│   │   │   ├── upload/
│   │   │   │   ├── FileUploader.tsx
│   │   │   │   ├── DragDropZone.tsx
│   │   │   │   ├── UploadProgress.tsx
│   │   │   │   └── FileList.tsx
│   │   │   │
│   │   │   ├── citation/
│   │   │   │   ├── CitationPanel.tsx
│   │   │   │   ├── CitationItem.tsx
│   │   │   │   ├── CitationBadge.tsx
│   │   │   │   └── SourceViewer.tsx
│   │   │   │
│   │   │   └── collections/
│   │   │       ├── CollectionList.tsx
│   │   │       ├── CollectionCard.tsx
│   │   │       ├── CollectionForm.tsx
│   │   │       └── DocumentSelector.tsx
│   │   │
│   │   ├── layouts/
│   │   │   ├── MainLayout.tsx
│   │   │   ├── AuthLayout.tsx
│   │   │   └── ChatLayout.tsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   ├── useChat.ts
│   │   │   ├── useFetch.ts
│   │   │   ├── useModal.ts
│   │   │   ├── usePagination.ts
│   │   │   └── useDebounce.ts
│   │   │
│   │   ├── services/
│   │   │   ├── api/
│   │   │   │   ├── api_client.ts
│   │   │   │   ├── auth_api.ts
│   │   │   │   ├── document_api.ts
│   │   │   │   ├── chat_api.ts
│   │   │   │   ├── collection_api.ts
│   │   │   │   ├── search_api.ts
│   │   │   │   └── upload_api.ts
│   │   │   │
│   │   │   ├── storage/
│   │   │   │   ├── localStorage.ts
│   │   │   │   └── sessionStorage.ts
│   │   │   │
│   │   │   └── notification/
│   │   │       └── notificationService.ts
│   │   │
│   │   ├── context/
│   │   │   ├── AuthContext.tsx
│   │   │   ├── ChatContext.tsx
│   │   │   ├── CollectionContext.tsx
│   │   │   ├── NotificationContext.tsx
│   │   │   └── GlobalContext.tsx
│   │   │
│   │   ├── types/
│   │   │   ├── api.ts
│   │   │   ├── auth.ts
│   │   │   ├── chat.ts
│   │   │   ├── document.ts
│   │   │   ├── collection.ts
│   │   │   ├── common.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── constants/
│   │   │   ├── api_endpoints.ts
│   │   │   ├── app_config.ts
│   │   │   ├── error_messages.ts
│   │   │   └── ui_constants.ts
│   │   │
│   │   ├── utils/
│   │   │   ├── validators.ts
│   │   │   ├── formatters.ts
│   │   │   ├── api_utils.ts
│   │   │   ├── storage_utils.ts
│   │   │   └── date_utils.ts
│   │   │
│   │   ├── styles/
│   │   │   ├── globals.css
│   │   │   ├── variables.css
│   │   │   ├── themes.css
│   │   │   ├── animations.css
│   │   │   └── components/
│   │   │       ├── chat.css
│   │   │       ├── upload.css
│   │   │       ├── citation.css
│   │   │       └── collections.css
│   │   │
│   │   └── assets/
│   │       ├── icons/
│   │       │   ├── chat_icon.svg
│   │       │   ├── upload_icon.svg
│   │       │   ├── search_icon.svg
│   │       │   ├── settings_icon.svg
│   │       │   └── (other icons)
│   │       │
│   │       └── images/
│   │           ├── logo.png
│   │           ├── hero.png
│   │           └── (other images)
│   │
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── components.test.tsx
│   │   │   ├── hooks.test.ts
│   │   │   ├── utils.test.ts
│   │   │   └── services.test.ts
│   │   │
│   │   └── integration/
│   │       ├── chat_flow.test.tsx
│   │       ├── upload_flow.test.tsx
│   │       ├── auth_flow.test.tsx
│   │       └── search_flow.test.tsx
│   │
│   └── __tests__/
│       ├── setup.ts
│       └── mocks/
│
├── infrastructure/
│   ├── docker/
│   │   ├── Dockerfile.backend
│   │   ├── Dockerfile.frontend
│   │   ├── docker-compose.yml
│   │   ├── docker-compose.prod.yml
│   │   └── nginx/
│   │       ├── nginx.conf
│   │       └── ssl/
│   │
│   ├── kubernetes/
│   │   ├── backend-deployment.yaml
│   │   ├── frontend-deployment.yaml
│   │   ├── postgres-deployment.yaml
│   │   ├── redis-deployment.yaml
│   │   ├── chroma-deployment.yaml
│   │   ├── service.yaml
│   │   └── ingress.yaml
│   │
│   └── scripts/
│       ├── setup.sh
│       ├── install_dependencies.sh
│       ├── run_migrations.sh
│       ├── init_db.sh
│       ├── deploy.sh
│       └── health_check.sh
│
├── docs/
│   ├── README.md
│   ├── API_DOCUMENTATION.md
│   ├── ARCHITECTURE.md
│   ├── SETUP_GUIDE.md
│   ├── DEPLOYMENT_GUIDE.md
│   ├── DATABASE_SCHEMA.md
│   ├── RAG_PIPELINE.md
│   ├── API_ENDPOINTS.md
│   ├── TESTING_GUIDE.md
│   ├── CONFIGURATION.md
│   └── TROUBLESHOOTING.md
│
├── .gitignore
├── .env.local
├── docker-compose.yml
├── README.md
└── requirements.txt (root level)

================================
BACKEND MODULES BREAKDOWN:
================================

api/routes/
  → auth.py: User login, register, token refresh
  → documents.py: Upload, delete, list documents
  → collections.py: CRUD collections/workspaces
  → chat.py: Chat endpoints
  → search.py: Semantic search endpoints
  → health.py: Health check endpoints

rag/loaders/
  → pdf_loader.py: PDF document loading
  → docx_loader.py: DOCX document loading
  → base_loader.py: Abstract loader interface

rag/chunking/
  → chunker_strategy.py: Chunking strategy pattern
  → semantic_chunker.py: Semantic-aware chunking
  → recursive_chunker.py: Recursive character-level chunking

rag/embeddings/
  → embedding_service.py: Embedding operations
  → model_manager.py: Model lifecycle management

rag/vectorstore/
  → chroma_store.py: ChromaDB operations
  → base_vectorstore.py: Abstract vectorstore interface
  → collection_manager.py: Collection management

rag/retrievers/
  → semantic_retriever.py: Semantic search retrieval
  → hybrid_retriever.py: Hybrid retrieval (semantic + keyword)
  → base_retriever.py: Abstract retriever interface

rag/pipelines/
  → ingestion_pipeline.py: Document ingestion workflow
  → qa_pipeline.py: QA retrieval-augmented pipeline
  → citation_pipeline.py: Citation extraction pipeline

rag/prompts/
  → qa_prompts.py: QA prompt templates
  → system_prompts.py: System-level prompts
  → prompt_templates.py: Template management

rag/llm/
  → ollama_client.py: Ollama API client
  → llm_service.py: LLM operations
  → response_parser.py: Response parsing/formatting

services/
  → document_service.py: Document management logic
  → collection_service.py: Collection operations
  → chat_service.py: Chat history & management
  → citation_service.py: Citation extraction & tracking
  → search_service.py: Search orchestration
  → upload_service.py: File upload handling
  → cache_service.py: Caching layer
  → auth_service.py: Authentication logic

db/models/
  → user.py: User model
  → document.py: Document model
  → collection.py: Collection/workspace model
  → chat_message.py: Chat message model
  → chat_session.py: Chat session model
  → base.py: Base SQLAlchemy model

schemas/
  → Pydantic schemas for API request/response validation

tests/
  → Comprehensive unit & integration tests
  → Test fixtures & mock data

config/
  → settings.py: Application configuration
  → database_config.py: Database configuration
  → logging_config.py: Logging setup

================================
FRONTEND MODULES BREAKDOWN:
================================

pages/
  → Dashboard: Main user dashboard
  → Chat: Chat interface page
  → Collections: Collections management page
  → Search: Advanced search page
  → Documents: Document management page
  → Auth: Login/Register pages
  → NotFound: 404 page

components/common/
  → Reusable UI components
  → Header, Sidebar, Footer, Button, Modal, etc.

components/chat/
  → ChatWindow: Main chat container
  → ChatMessage: Individual message display
  → ChatInput: Message input box
  → MessageList: Message list rendering
  → ChatHistory: Chat history sidebar

components/upload/
  → FileUploader: Upload handler
  → DragDropZone: Drag-drop interface
  → UploadProgress: Progress indicator
  → FileList: Uploaded files list

components/citation/
  → CitationPanel: Citation display panel
  → CitationItem: Individual citation
  → CitationBadge: Citation indicator badge
  → SourceViewer: Source document viewer

components/collections/
  → CollectionList: Collections listing
  → CollectionCard: Collection display card
  → CollectionForm: Create/edit form
  → DocumentSelector: Document selection UI

hooks/
  → useAuth: Authentication hook
  → useChat: Chat operations hook
  → useFetch: Data fetching hook
  → useModal: Modal state management
  → usePagination: Pagination logic
  → useDebounce: Debounce utility hook

services/api/
  → api_client.ts: Axios instance configuration
  → auth_api.ts: Authentication endpoints
  → document_api.ts: Document operations
  → chat_api.ts: Chat endpoints
  → collection_api.ts: Collection endpoints
  → search_api.ts: Search endpoints
  → upload_api.ts: Upload endpoints

context/
  → React Context for global state management
  → AuthContext, ChatContext, CollectionContext, etc.

types/
  → TypeScript type definitions
  → API response types, domain models, etc.

utils/
  → Utility functions for validation, formatting, etc.

styles/
  → Global CSS & Tailwind configuration
  → Component-specific styles
  → Theme variables & animations

================================
SCALABILITY CONSIDERATIONS:
================================

✓ Modular architecture for independent deployment
✓ Service layer abstraction for business logic
✓ Repository pattern for data access
✓ Middleware for cross-cutting concerns
✓ Configuration management for multi-environment
✓ Database migrations for schema versioning
✓ Comprehensive testing structure
✓ Docker/Kubernetes ready
✓ API versioning support
✓ JWT authentication for security
✓ Cache layer for performance
✓ Logging for observability
✓ Error handling middleware
✓ CORS configuration
✓ Multi-tenant collection support
✓ Vector store isolation by collection
