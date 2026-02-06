from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Mapping, Sequence, TypedDict

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_google_vertexai import ChatVertexAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
import requests

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("Please install PyYAML: pip install pyyaml") from exc

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
    ingest_url = str(raw.get("ingest_url",  "http://localhost:8000/ingestion/runs")) 
    repo_url = str(raw.get("repo_url",  "https://github.com/emilybache/Racing-Car-Katas.git")) 

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
        working_directory=str(cfg.working_directory).rstrip("/"),
        source_dir=cfg.source_dir.lstrip("./"),
        target_dir=cfg.target_dir.lstrip("./"),
        repo_dir=cfg.repo_dir.lstrip("./"),
    )


# =========================
# Initialization
# =========================


def init_file_management_tools(cfg: AppConfig, log: LogPacker):
    """Initializes file management tools within the configured root directory."""

    log.info(f"Initializing file system tools. root_dir={cfg.working_directory}")
    toolkit = FileManagementToolkit(root_dir=str(cfg.working_directory))
    return toolkit.get_tools()


def init_llms(cfg: AppConfig, log: LogPacker):
    """Initializes architect/engineer LLMs."""

    log.info("Initializing architect LLM (Architect)...")
    llm_architect = ChatVertexAI(
        model=cfg.architect.model,
        project=cfg.architect.project,
        # location=cfg.architect.location,
        temperature=cfg.architect.temperature,
    )

    log.info("Initializing engineer LLM (Engineer)...")
    llm_engineer = ChatVertexAI(
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
    llm_architect: ChatVertexAI,
    llm_engineer: ChatVertexAI,
    log: LogPacker,
):
    """Builds and compiles the LangGraph workflow."""

    architect_prompt_raw = load_prompt(cfg.prompts.architect_path)
    engineer_prompt_raw = load_prompt(cfg.prompts.engineer_path)

    engineer_system_prompt = engineer_prompt_raw.format(
        working_directory=str(cfg.working_directory).rstrip("/"),
        target_dir=cfg.target_dir.lstrip("./"),
        # 如果需要 source_dir 或 repo_dir 也可以加進來
        # source_dir=cfg.source_dir,
    )

    architect_system_prompt = architect_prompt_raw.format(
        working_directory=str(cfg.working_directory).rstrip("/"),
        # repo_dir=cfg.repo_dir.lstrip("./"),
        
        # 如果需要 source_dir 或 repo_dir 也可以加進來
        source_dir=cfg.source_dir,
    )

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
        result = llm_engineer_with_tools.invoke(
            {
                "messages": [HumanMessage(content=request)],
                "config": {"recursion_limit": 100},
            }
        )
        return str(result["messages"][-1].content)

    llm_architect_with_tools = create_agent(
        llm_architect,
        tools=tools + [refactor_code],
        system_prompt=architect_system_prompt,
    )

    def architect_node(state: AgentState):
        """Architect node: produces a step-by-step plan (no tool calls)."""

        messages = state["messages"]
        response = llm_architect_with_tools.invoke(
            {"messages": messages},  # 這是 Input
            {"recursion_limit": 100},  # 這是 Config
        )
        print(response)
        return {"messages": [response["messages"][-1]]}

    workflow = StateGraph(AgentState)
    workflow.add_node("architect", architect_node)
    workflow.set_entry_point("architect")
    workflow.add_edge("architect", END)

    log.info("Compiling LangGraph workflow...")
    return workflow.compile()


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
        default="config.yaml",
        help="Path to YAML config (default: config.yaml)",
    )
    return parser.parse_args(argv)


def stream_pretty(app, user_input: str, log: LogPacker) -> None:
    """Streams the graph execution with basic formatting.

    Note:
        This workflow calls the Architect exactly once at the start. All later
        AI messages come from the Engineer (potentially across multiple tool
        iterations). We use that invariant for simple role labeling.

    Args:
        app: Compiled LangGraph application.
        user_input: User request prompt content.
        log: Logger wrapper.
    """

    inputs = {"messages": [HumanMessage(content=user_input)]}

    seen_architect = False

    for event in app.stream(inputs, stream_mode="values"):
        last_msg = event["messages"][-1]

        if last_msg.type == "ai":
            if not seen_architect:
                role = "Architect"
                seen_architect = True
            else:
                role = "Engineer"

            log.info(f"[{role}] {last_msg.content}")
            if getattr(last_msg, "tool_calls", None):
                tool_names = [t.get("name", "") for t in last_msg.tool_calls]
                log.info(f"[Engineer] tool_calls={tool_names}")

        elif last_msg.type == "tool":
            # Tool output may be huge; record length only.
            log.info(f"[Tool] returned_len={len(str(last_msg.content))}")


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point."""

    load_dotenv()

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
        response = requests.post(ingest_url, json=data)

        # 檢查請求是否成功 (狀態碼為 2xx)
        response.raise_for_status()

        # 輸出回傳結果
        print("狀態碼:", response.status_code)
        print("回傳內容:", response.json())

    except requests.exceptions.RequestException as e:
        print(f"發送請求時發生錯誤: {e}")


    tools = init_file_management_tools(cfg, log)
    llm_architect, llm_engineer = init_llms(cfg, log)
    app = build_graph(cfg, tools, llm_architect, llm_engineer, log)
    # app.get_graph().print_ascii()
    user_input = render_user_input(cfg)
    log.info("Starting multi-agent execution...")
    stream_pretty(app, user_input, log)
    log.info(f"Done. Check target directory: {cfg.target_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
