"""Vertex AI Gemini LLM adapter。

將 Vertex AI GenerativeModel 包裝為 test_gen 模組的 LLMClient 介面。

用法::

    from runner.test_gen.llm_adapter import create_vertex_client

    client = create_vertex_client()
    response = client.generate("Hello")
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 已知的 GCP key file 路徑（專案內）
_DEFAULT_KEY_PATH = Path(
    ""
)


@dataclass
class VertexLLMClient:
    """Vertex AI Gemini 的 LLMClient 實作。

    符合 ``guidance_gen.LLMClient`` Protocol。

    Args:
        model_name: Gemini 模型名稱。
        project_id: GCP project ID（None 則自動偵測）。
        location: GCP region。
        system_instruction: 系統指令（角色定義和行為準則）。
    """

    model_name: str = "gemini-2.5-pro"
    project_id: str | None = None
    location: str = "us-central1"
    system_instruction: str | None = None
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
        self._model = GenerativeModel(
            self.model_name,
            system_instruction=self.system_instruction,
        )

    def generate(
        self, prompt: str, max_retries: int = 5, system_override: str | None = None
    ) -> str:
        """送出 prompt 並取得回應文字，含 429 retry。

        Args:
            prompt: User prompt 文字。
            max_retries: 最大重試次數。
            system_override: 臨時 system instruction（覆蓋預設）。

        Returns:
            LLM 回應文字。
        """
        self._ensure_init()

        # 如果有 system_override，創建臨時 model
        if system_override:
            from vertexai.generative_models import GenerativeModel

            model = GenerativeModel(self.model_name, system_instruction=system_override)
        else:
            model = self._model

        for attempt in range(max_retries + 1):
            try:
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as exc:
                if "429" in str(exc) or "ResourceExhausted" in type(exc).__name__:
                    wait = 2**attempt * 5  # 5, 10, 20, 40, 80 秒
                    logger.warning(
                        "Rate limited (attempt %d/%d), waiting %ds...",
                        attempt + 1,
                        max_retries + 1,
                        wait,
                    )
                    time.sleep(wait)
                    continue
                raise
        raise RuntimeError(f"Rate limited after {max_retries + 1} attempts")


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
