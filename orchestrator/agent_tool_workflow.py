from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Mapping, Sequence, TypedDict

import requests
from dotenv import load_dotenv

# NOTE: langchain.agents.create_agent (v1.2.9+) 已內建 tool loop，
# 會自動處理 tool calls 直到 LLM 停止呼叫 tools
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.messages import BaseMessage, HumanMessage

# from langchain_google_vertexai import ChatVertexAI
from langchain_google_genai import ChatGoogleGenerativeAI

# NOTE: 移除未使用的 StateGraph/END import，因為 create_agent 已經返回 compiled graph
# 保留 add_messages 供 AgentState 使用
from langgraph.graph.message import add_messages

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("Please install PyYAML: pip install pyyaml") from exc
import sys


def ensure_repo_root_on_path() -> Path:
    """確保 repo root 已加入 sys.path。

    Returns:
        repo root 路徑。
    """
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.append(str(repo_root))
    return repo_root


ensure_repo_root_on_path()
# ruff: noqa: F401
from runner.test_gen.pipeline_tool import generate_test  # noqa

# =========================
# Token Estimation Logic
# =========================


def estimate_tokens(file_path: str) -> int:
    """
    透過檔案大小粗略估計 Token 數量。
    估算標準：1 Token ≈ 4 Bytes (適用於英文/程式碼/JSON)
    """
    try:
        if not os.path.exists(file_path):
            return 0
        file_size_bytes = os.path.getsize(file_path)
        return int(file_size_bytes / 4)
    except Exception:
        return 0


# =========================
# Data models
# =========================


@dataclass(frozen=True)
class LlmConfig:
    """LLM configuration for a ChatVertexAI model."""

    model: str
    project: str
    location: str
    temperature: float = 0.0


@dataclass(frozen=True)
class PromptConfig:
    """Prompt file paths."""

    architect_path: Path
    engineer_path: Path


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    working_directory: Path
    ingest_url: str
    repo_url: str
    architect: LlmConfig
    engineer: LlmConfig
    prompts: PromptConfig
    source_dir: str
    target_dir: str
    repo_dir: str
    user_input_template: str
    log_filename: str = "multi_agent.log"


class AgentState(TypedDict):
    """LangGraph state containing the conversation history."""

    messages: Annotated[list[BaseMessage], add_messages]


# =========================
# Logging ("logger packer")
# =========================


class LogPacker:
    """Thin logging wrapper with a consistent, hackathon-friendly format.

    This intentionally stays minimal: file + console handlers, and a few
    helper methods for structured logging.
    """

    def __init__(self, log_path: Path) -> None:
        import logging

        self._logger = logging.getLogger("multi_agent")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        # Avoid duplicate handlers if re-imported (e.g., notebooks).
        if self._logger.handlers:
            return

        log_path.parent.mkdir(parents=True, exist_ok=True)

        fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(fmt)
        self._logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(fmt)
        self._logger.addHandler(console_handler)

    def info(self, msg: str) -> None:
        """Logs an informational message."""

        self._logger.info(msg)

    def warning(self, msg: str) -> None:
        """Logs a warning message."""

        self._logger.warning(msg)

    def error(self, msg: str) -> None:
        """Logs an error message."""

        self._logger.error(msg)

    def json(self, label: str, payload: Mapping[str, object]) -> None:
        """Logs a JSON-serializable payload in a single line."""

        self._logger.info("%s: %s", label, json.dumps(payload, ensure_ascii=False))


# =========================
# Config / prompts
# =========================


def load_yaml_config(config_path: Path) -> dict:
    """Loads YAML config from disk.

    Args:
        config_path: Path to a YAML file.

    Returns:
        Parsed config as a dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the YAML is empty or invalid.
    """

    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML config (expected mapping): {config_path}")
    return data


def _as_path(base_dir: Path, raw: str) -> Path:
    """Resolves a possibly-relative path against a base directory."""

    p = Path(raw)
    return p if p.is_absolute() else (base_dir / p)


def parse_app_config(config_path: Path) -> AppConfig:
    """Parses an AppConfig from a YAML file.

    Args:
        config_path: Path to the YAML config file.

    Returns:
        AppConfig instance.
    """

    raw = load_yaml_config(config_path)
    base_dir = config_path.parent

    working_directory = _as_path(
        base_dir, str(raw.get("working_directory", "."))
    ).resolve()
    ingest_url = str(raw.get("ingest_url", "http://localhost:8000/ingestion/runs"))
    repo_url = str(
        raw.get("repo_url", "https://github.com/emilybache/Racing-Car-Katas.git")
    )

    architect_raw = (
        raw.get("llm", {}).get("architect", {})
        if isinstance(raw.get("llm"), dict)
        else {}
    )
    engineer_raw = (
        raw.get("llm", {}).get("engineer", {})
        if isinstance(raw.get("llm"), dict)
        else {}
    )

    prompts_raw = raw.get("prompts", {}) if isinstance(raw.get("prompts"), dict) else {}

    architect = LlmConfig(
        model=str(architect_raw.get("model", "qwen/qwen3-next-80b-a3b-thinking-maas")),
        project=str(architect_raw.get("project", "tsmchaker")),
        location=str(architect_raw.get("location", "global")),
        temperature=float(architect_raw.get("temperature", 0.0)),
    )
    engineer = LlmConfig(
        model=str(engineer_raw.get("model", "gemini-2.5-pro")),
        project=str(engineer_raw.get("project", "tsmchaker")),
        location=str(engineer_raw.get("location", "global")),
        temperature=float(engineer_raw.get("temperature", 0.0)),
    )

    prompts = PromptConfig(
        architect_path=_as_path(
            base_dir, str(prompts_raw.get("architect", "prompts/architect.md"))
        ),
        engineer_path=_as_path(
            base_dir, str(prompts_raw.get("engineer", "prompts/engineer.md"))
        ),
    )

    source_dir = str(raw.get("source_dir", "./Racing-Car-Katas/Python"))
    target_dir = str(raw.get("target_dir", "./refactor-golang"))
    repo_dir = str(raw.get("repo_dir", "./artifacts/caa0ea0651474be18c2f4c265c32b9eb"))
    user_input_template = str(
        raw.get(
            "user_input_template",
            "Refactor the codebase located in {working_directory}/{source_dir} "
            "into Golang. "
            "Output the new code to the "
            "{working_directory}/{target_dir} directory. "
            "Requirement: "
            "Preserve the exact business logic "
            "and include meaningful comments.",
        )
    )
    log_filename = str(raw.get("log_filename", "multi_agent.log"))

    return AppConfig(
        working_directory=working_directory,
        ingest_url=ingest_url,
        repo_url=repo_url,
        architect=architect,
        engineer=engineer,
        prompts=prompts,
        source_dir=source_dir,
        target_dir=target_dir,
        repo_dir=repo_dir,
        user_input_template=user_input_template,
        log_filename=log_filename,
    )


def load_prompt(prompt_path: Path) -> str:
    """Loads a prompt file from disk.

    Args:
        prompt_path: Path to a UTF-8 text prompt file (recommended: .md).

    Returns:
        Prompt content as a string.
    """

    return prompt_path.read_text(encoding="utf-8").strip()


def render_user_input(cfg: AppConfig) -> str:
    """Renders the user input prompt from template + YAML parameters."""

    return cfg.user_input_template.format(
        source_dir=cfg.source_dir.lstrip("./"),
        target_dir=cfg.target_dir.lstrip("./"),
        repo_dir=cfg.repo_dir.lstrip("./"),
    )


# =========================
# Initialization
# =========================


def init_file_management_tools(cfg: AppConfig, log: LogPacker):
    """
    Initializes file system tools with Wrappers:
    1. Read: Checks token limits (Safety).
    2. Write: Logs the file path (Transparency).
    """
    log.info(f"Initializing file system tools. root_dir={cfg.working_directory}")

    # 1. 取得原廠標準工具
    toolkit = FileManagementToolkit(root_dir=str(cfg.working_directory))
    std_tools = toolkit.get_tools()

    # ============================
    # Wrapper 1: Safe Read File
    # ============================
    original_read_tool = next((t for t in std_tools if t.name == "read_file"), None)

    # 預設使用原廠工具，稍後如果有定義 wrapper 則替換
    final_read_tool = original_read_tool

    if original_read_tool:

        @tool("read_file")
        def safe_read_wrapper(file_path: str) -> str:
            """
            Read a file from the filesystem.
            Input: file_path (str)
            (Wrapper: Checks size first, then delegates to standard tool or truncates)
            """
            try:
                # A. 計算絕對路徑
                target_path = (cfg.working_directory / file_path).resolve()

                # 安全檢查
                if not str(target_path).startswith(
                    str(cfg.working_directory.resolve())
                ):
                    return f"Error: Access denied. Path {file_path} \
                    is outside the working directory."

                if not target_path.exists():
                    return f"Error: File {file_path} does not exist."

                # B. 檢查大小 (Token 估算)
                est_tokens = estimate_tokens(str(target_path))
                MAX_TOKENS = 300000

                if est_tokens > MAX_TOKENS:
                    read_chars = MAX_TOKENS * 4
                    log.warning(
                        f"🛡️ [SafeGuard] Intercepted large file:\
                         {file_path} (~{est_tokens} tokens). Truncating."
                    )
                    with open(
                        target_path, "r", encoding="utf-8", errors="replace"
                    ) as f:
                        preview = f.read(read_chars)
                    return (
                        f"{preview}\n\n"
                        f"====================================================\n"
                        f"[SYSTEM WARNING] File content truncated.\n"
                        f"Original size: ~{est_tokens} tokens. Limit: {MAX_TOKENS}.\n"
                        f"===================================================="
                    )

                # D. 呼叫原廠工具
                log.info(f"📄 [Read File] Reading {file_path} (~{est_tokens} tokens)")
                return original_read_tool.invoke(file_path)

            except Exception as e:
                error_msg = f"Error in safe_read_wrapper: {e}"
                log.error(error_msg)
                return error_msg

        final_read_tool = safe_read_wrapper

    # ============================
    # Wrapper 2: Log Write File  <-- 新增的部分
    # ============================
    original_write_tool = next((t for t in std_tools if t.name == "write_file"), None)

    final_write_tool = original_write_tool

    if original_write_tool:

        @tool("write_file")
        def write_log_wrapper(file_path: str, text: str) -> str:
            """
            Write a file to the filesystem.
            Input: file_path (str), text (str) - The content to write.
            (Wrapper: Logs the write action with path)
            """
            # 在這裡加上 Log
            log.info(f"💾 [Write File] Saving content to: {file_path}")

            try:
                # 呼叫原廠工具執行真正的寫入
                # 注意: write_file 通常需要傳入字典參數
                return original_write_tool.invoke(
                    {"file_path": file_path, "text": text}
                )
            except Exception as e:
                error_msg = f"Error writing file {file_path}: {e}"
                log.error(f"❌ [Write File] Failed: {error_msg}")
                return error_msg

        final_write_tool = write_log_wrapper

    # ============================
    # 3. 組裝最終工具列表
    # ============================
    final_tools = []
    for t in std_tools:
        if t.name == "read_file":
            if final_read_tool:
                final_tools.append(final_read_tool)
        elif t.name == "write_file":
            if final_write_tool:
                final_tools.append(final_write_tool)
        else:
            final_tools.append(t)

    return final_tools


def init_llms(cfg: AppConfig, log: LogPacker):
    """Initializes architect/engineer LLMs."""

    log.info("Initializing architect LLM (Architect)...")
    llm_architect = ChatGoogleGenerativeAI(
        model=cfg.architect.model,
        project=cfg.architect.project,
        # location=cfg.architect.location,
        temperature=cfg.architect.temperature,
    )

    log.info("Initializing engineer LLM (Engineer)...")
    llm_engineer = ChatGoogleGenerativeAI(
        model=cfg.engineer.model,
        project=cfg.engineer.project,
        # location=cfg.engineer.location,
        temperature=cfg.engineer.temperature,
    )

    # llm_architect = ChatGoogleGenerativeAI(
    #     model="gemini-2.5-pro",
    #     google_api_key=os.getenv("GOOGLE_API_KEY", "YOUR_KEY_HERE"),
    #     temperature=0,
    # )
    # llm_engineer = ChatGoogleGenerativeAI(
    #     model="gemini-2.5-flash",
    #     google_api_key=os.getenv("GOOGLE_API_KEY", "YOUR_KEY_HERE"),
    #     temperature=0,
    # )

    return llm_architect, llm_engineer


def build_graph(
    cfg: AppConfig,
    tools,
    llm_architect: ChatGoogleGenerativeAI,
    llm_engineer: ChatGoogleGenerativeAI,
    log: LogPacker,
):
    """Builds and compiles the LangGraph workflow.

    架構說明：
    - create_agent() 已內建 tool loop（會自動迭代執行 tool calls 直到 LLM 停止）
    - Architect 是主要 agent，負責規劃和協調
    - Engineer 透過 refactor_code tool 被 Architect 呼叫，執行實際重構
    - generate_test tool 用於執行 characterization testing pipeline

    工作流程：
    1. Architect 讀取 dependency graph 和 codebase
    2. Architect 建立 spec.md 規劃文件
    3. Architect 呼叫 refactor_code() 委派重構任務給 Engineer
    4. Engineer 使用 file tools 執行重構
    5. Architect 呼叫 generate_test() 執行測試
    6. 重複 3-5 直到所有 stage 完成
    """

    architect_prompt_raw = load_prompt(cfg.prompts.architect_path)
    engineer_prompt_raw = load_prompt(cfg.prompts.engineer_path)

    engineer_system_prompt = engineer_prompt_raw.format(
        # working_directory=str(cfg.working_directory).rstrip("/"),
        target_dir=cfg.target_dir.lstrip("./"),
        # 如果需要 source_dir 或 repo_dir 也可以加進來
        # source_dir=cfg.source_dir,
    )

    architect_system_prompt = architect_prompt_raw.format(
        # working_directory=str(cfg.working_directory).rstrip("/"),
        # repo_dir=cfg.repo_dir.lstrip("./"),
        # 如果需要 source_dir 或 repo_dir 也可以加進來
        source_dir=cfg.source_dir,
    )

    # NOTE: Engineer agent - create_agent 返回的是已編譯的 graph，
    # 內部已處理 tool loop（LLM → tool call → tool result → LLM → ...）
    llm_engineer_with_tools = create_agent(
        llm_engineer,
        tools=tools,
        system_prompt=engineer_system_prompt,
    )

    @tool
    def refactor_code(request: str) -> str:
        """
        Refactor or modify existing code based on natural language instructions.

        Use this tool when the user requests structural changes,
        performance optimization, or logic modifications to their codebase.
        It acts as a bridge between high-level
        intent and technical code execution.

        Input: Natural language refactor code request
        (e.g., 'refactor code in the ./python to JAVA')
        """
        log.info(
            f"➡️ [Next Step] Architect is delegating "
            f"task to Engineer. Request: {request[:100]}..."
        )

        # NOTE: config 應作為 invoke() 的第二個參數，不是 input dict 的一部分
        # recursion_limit 控制最大迭代次數（防止無限 loop）
        result = llm_engineer_with_tools.invoke(
            {"messages": [HumanMessage(content=request)]},
            {"recursion_limit": 100},
        )

        log.info(
            "⬅️ [Next Step] Engineer finished task. Returning result to Architect..."
        )

        # 返回 Engineer 的最終回覆（tool loop 結束後的 AI message）
        final_message = result["messages"][-1]
        return str(final_message.content)

    # NOTE: Architect agent 擁有：
    # - file tools (read_file, write_file, list_directory, etc.)
    # - refactor_code: 委派重構任務給 Engineer
    # - generate_test: 執行 characterization testing pipeline
    llm_architect_with_tools = create_agent(
        llm_architect,
        tools=tools + [refactor_code, generate_test],
        system_prompt=architect_system_prompt,
    )

    log.info(
        "Compiling LangGraph workflow (using create_agent with built-in tool loop)..."
    )

    # NOTE: 直接返回 architect agent graph
    # create_agent 已經是完整的 compiled graph，包含：
    # - agent node: 呼叫 LLM
    # - tools node: 執行 tool calls
    # - conditional edge: 判斷是否繼續 loop
    # 不需要再用 StateGraph 包裝
    return llm_architect_with_tools


# =========================
# Runtime / main
# =========================


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parses CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Multi-agent refactoring orchestrator (LangGraph)."
    )

    parser.add_argument(
        "--config",
        type=str,
        default="/app/orchestrator/config.yaml",
        help="Path to YAML config (default: config.yaml)",
    )
    return parser.parse_args(argv)


def stream_pretty(app, user_input: str, log: LogPacker) -> None:
    """Streams the graph execution with basic formatting.

    NOTE: 使用 create_agent 後，所有 AI messages 都來自 Architect agent。
    當 Architect 呼叫 refactor_code tool 時，Engineer 的執行是同步的，
    其輸出會作為 tool result 返回，不會產生獨立的 AI message。

    訊息流程：
    1. AI (Architect) - 可能包含 tool_calls
    2. Tool - tool 執行結果（包含 refactor_code/generate_test 的輸出）
    3. AI (Architect) - 處理 tool 結果，可能繼續呼叫 tools
    4. ... 重複直到 Architect 不再呼叫 tools

    Args:
        app: Compiled LangGraph application (from create_agent).
        user_input: User request prompt content.
        log: Logger wrapper.
    """

    inputs = {"messages": [HumanMessage(content=user_input)]}

    log.info(
        "🚀 [Next Step] Injecting user input into the Graph and starting execution..."
    )

    # NOTE: 追蹤迭代次數，用於 debug
    iteration_count = 0

    for event in app.stream(inputs, {"recursion_limit": 100}, stream_mode="values"):
        iteration_count += 1
        last_msg = event["messages"][-1]

        if last_msg.type == "ai":
            # NOTE: 所有 AI messages 都來自 Architect（Engineer 透過 tool 執行）
            role = "Architect"

            if getattr(last_msg, "tool_calls", None):
                tool_names = [t.get("name", "") for t in last_msg.tool_calls]
                log.info(
                    f"🛠️ [Iteration {iteration_count}]\
                    {role} calling tools: {tool_names}"
                )

                # 特別標記委派給 Engineer 的情況
                if "refactor_code" in tool_names:
                    log.info("   ↳ Delegating refactoring task to Engineer...")
                if "generate_test" in tool_names:
                    log.info("   ↳ Triggering characterization testing pipeline...")
            else:
                log.info(f"💬 [Iteration {iteration_count}] {role} responding...")

            # 輸出 AI 訊息內容(截斷過長內容)
            content = str(last_msg.content)
            if len(content) > 500:
                log.info(
                    f"[{role}] {content[:500]}... \
                    (truncated, total {len(content)} chars)"
                )
            else:
                log.info(f"[{role}] {content}")

        elif last_msg.type == "tool":
            # Tool 執行結果
            tool_name = getattr(last_msg, "name", "unknown")
            content_len = len(str(last_msg.content))

            log.info(
                f"✅ [Iteration {iteration_count}] Tool '{tool_name}' completed. "
                f"Output length: {content_len} chars"
            )

            # 對於重要 tools，輸出更多細節
            if tool_name in ("refactor_code", "generate_test"):
                content = str(last_msg.content)
                if len(content) > 300:
                    log.info(f"   ↳ Result preview: {content[:300]}...")
                else:
                    log.info(f"   ↳ Result: {content}")

        elif last_msg.type == "human":
            # 初始 user input（通常只有第一次）
            log.info(f"👤 [Iteration {iteration_count}] User input received")

    log.info(f"🏁 Graph execution completed after {iteration_count} iterations")


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point."""

    load_dotenv()
    print("📋 [Next Step] Loading configuration and arguments...")

    args = parse_args(argv)
    cfg = parse_app_config(Path(args.config).resolve())

    log = LogPacker(cfg.working_directory / cfg.log_filename)
    log.json(
        "config",
        {
            "working_directory": str(cfg.working_directory),
            "architect_model": cfg.architect.model,
            "engineer_model": cfg.engineer.model,
            "prompts": {
                "architect": str(cfg.prompts.architect_path),
                "engineer": str(cfg.prompts.engineer_path),
            },
        },
    )

    # 設定 API 端點網址
    ingest_url = cfg.ingest_url

    # 設定要傳送的資料 (Payload)
    data = {
        "repo_url": cfg.repo_url,
        "start_prompt": "Start processing",
        "options": {},
        "save_path": "/workspace/init",
    }

    try:
        # 發送 POST 請求
        # 使用 json= 參數會自動將字典轉換為 JSON 字串，並加上正確的 Header
        log.info(f"📡 [Ingestion] Sending request to {ingest_url}...")
        response = requests.post(ingest_url, json=data)

        # 檢查請求是否成功 (狀態碼為 2xx)
        response.raise_for_status()

        # 輸出回傳結果
        log.info(f"✅ [Ingestion] Success - Status: {response.status_code}")
        log.json("ingestion_response", response.json())

    except requests.exceptions.RequestException as e:
        # NOTE: Ingestion 失敗是 critical error，workspace 未初始化
        # 後續的 file operations 會失敗，因此應該中止執行
        log.error(f"❌ [Ingestion] Failed: {e}")
        log.error("Aborting workflow - workspace not initialized")
        return 1

    log.info("🧰 [Next Step] Initializing file management tools & LLMs...")
    tools = init_file_management_tools(cfg, log)
    llm_architect, llm_engineer = init_llms(cfg, log)
    log.info("🏗️ [Next Step] Building the Agent Graph...")
    app = build_graph(cfg, tools, llm_architect, llm_engineer, log)
    # app.get_graph().print_ascii()
    user_input = render_user_input(cfg)
    log.info("▶️ [Next Step] Starting multi-agent execution loop...")
    stream_pretty(app, user_input, log)
    log.info(f"🏁 [Done] Execution finished. Check target directory: {cfg.target_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
