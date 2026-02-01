"""Vertex AI Gemini LLM adapter。

將 Vertex AI GenerativeModel 包裝為 test_gen 模組的 LLMClient 介面。

用法::

    from runner.test_gen.llm_adapter import create_vertex_client

    client = create_vertex_client()
    response = client.generate("Hello")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 已知的 GCP key file 路徑（專案內）
_DEFAULT_KEY_PATH = Path(
    "/home/yoyo/projects/TSMC-2026-Hackathon/hackathon-485006-fc9be8263cae.json"
)


@dataclass
class VertexLLMClient:
    """Vertex AI Gemini 的 LLMClient 實作。

    符合 ``guidance_gen.LLMClient`` Protocol。

    Args:
        model_name: Gemini 模型名稱。
        project_id: GCP project ID（None 則自動偵測）。
        location: GCP region。
    """

    model_name: str = "gemini-2.5-pro"
    project_id: str | None = None
    location: str = "us-central1"
    _model: Any = field(default=None, repr=False)

    def _ensure_init(self) -> None:
        """確保 Vertex AI 已初始化且 model 已載入。"""
        if self._model is not None:
            return

        import google.auth
        import vertexai
        from vertexai.generative_models import GenerativeModel

        # 自動設定 credentials
        env_key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not env_key and _DEFAULT_KEY_PATH.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_DEFAULT_KEY_PATH)

        credentials, project_id = google.auth.default()
        project = self.project_id or project_id
        vertexai.init(
            project=project,
            location=self.location,
            credentials=credentials,
        )
        self._model = GenerativeModel(self.model_name)

    def generate(self, prompt: str) -> str:
        """送出 prompt 並取得回應文字。

        Args:
            prompt: 完整 prompt 文字。

        Returns:
            LLM 回應文字。
        """
        self._ensure_init()
        response = self._model.generate_content(prompt)
        return response.text.strip()


def create_vertex_client(
    model_name: str = "gemini-2.5-pro",
    location: str = "us-central1",
) -> VertexLLMClient:
    """建立 Vertex AI LLM client 的便捷函式。

    Args:
        model_name: Gemini 模型名稱。
        location: GCP region。

    Returns:
        VertexLLMClient 實例。
    """
    return VertexLLMClient(model_name=model_name, location=location)
