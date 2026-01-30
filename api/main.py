from __future__ import annotations

from fastapi import FastAPI

from api.ingestion.routes import router as ingestion_router

"""API 服務入口點。"""
app = FastAPI(title="TSMC-2026-Hackathon API")
app.include_router(ingestion_router)
