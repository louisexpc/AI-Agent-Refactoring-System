from __future__ import annotations

from fastapi import FastAPI

from api.ingestion.routes import router as ingestion_router

"""API 服務入口點。"""
app = FastAPI(title="AI Agent Refactoring API")
app.include_router(ingestion_router)
