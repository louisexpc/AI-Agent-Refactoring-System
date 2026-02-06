"""Multi-agent refactoring orchestrator (LangGraph).

This script wires a two-role workflow (Architect -> Engineer) using LangGraph:
- Architect (Planner): produces a step-by-step plan (no tools).
- Engineer (Coder): executes the plan using file system tools.

Refactor notes (MVP):
- Runtime/config parameters are loaded from a YAML config file.
- Prompts are loaded from external prompt files (referenced in the YAML).
- Logging uses a small "logger packer" wrapper with sensible defaults.
- Initialization is decomposed into functions for clarity and testability.

This file intentionally does not introduce new product features; it only
refactors configuration, prompting, logging, and initialization structure.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, Mapping, Sequence, TypedDict

from dotenv import load_dotenv
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_google_vertexai import ChatVertexAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("Please install PyYAML: pip install pyyaml") from exc

from orchestrator.sandbox import (
    create_sandbox,
    execute_command_in_sandbox,
    remove_sandbox,
)

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
    planner: LlmConfig
    coder: LlmConfig
    prompts: PromptConfig
    source_dir: str
    target_dir: str
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

    planner_raw = (
        raw.get("llm", {}).get("planner", {})
        if isinstance(raw.get("llm"), dict)
        else {}
    )
    coder_raw = (
        raw.get("llm", {}).get("coder", {}) if isinstance(raw.get("llm"), dict) else {}
    )

    prompts_raw = raw.get("prompts", {}) if isinstance(raw.get("prompts"), dict) else {}

    planner = LlmConfig(
        model=str(planner_raw.get("model", "qwen/qwen3-next-80b-a3b-thinking-maas")),
        project=str(planner_raw.get("project", "tsmchaker")),
        location=str(planner_raw.get("location", "global")),
        temperature=float(planner_raw.get("temperature", 0.0)),
    )
    coder = LlmConfig(
        model=str(coder_raw.get("model", "gemini-2.5-pro")),
        project=str(coder_raw.get("project", "tsmchaker")),
        location=str(coder_raw.get("location", "global")),
        temperature=float(coder_raw.get("temperature", 0.0)),
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
    user_input_template = str(
        raw.get(
            "user_input_template",
            "Refactor the codebase located in "
            "{working_directory}/{source_dir} into Golang. "
            "Output the new code to the "
            "{working_directory}/{target_dir} directory. "
            "Requirement: Preserve the exact business "
            "logic and include meaningful comments.",
        )
    )
    log_filename = str(raw.get("log_filename", "multi_agent.log"))

    return AppConfig(
        working_directory=working_directory,
        planner=planner,
        coder=coder,
        prompts=prompts,
        source_dir=source_dir,
        target_dir=target_dir,
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
    )


# =========================
# Initialization
# =========================


def init_tools(cfg: AppConfig, log: LogPacker):
    """Initializes file management tools within the configured root directory."""

    log.info(f"Initializing file system tools. root_dir={cfg.working_directory}")
    toolkit = FileManagementToolkit(root_dir=str(cfg.working_directory))
    tools = toolkit.get_tools()

    # NOTE (added): expose Docker sandbox lifecycle tools to the Engineer.
    # These operate at VM-level via the Docker CLI.
    tools.extend([create_sandbox, execute_command_in_sandbox, remove_sandbox])
    return tools


def init_llms(cfg: AppConfig, log: LogPacker):
    """Initializes planner/coder LLMs."""

    log.info("Initializing planner LLM (Architect)...")
    llm_planner = ChatVertexAI(
        model=cfg.planner.model,
        project=cfg.planner.project,
        location=cfg.planner.location,
        temperature=cfg.planner.temperature,
    )

    log.info("Initializing coder LLM (Engineer)...")
    llm_coder = ChatVertexAI(
        model=cfg.coder.model,
        project=cfg.coder.project,
        location=cfg.coder.location,
        temperature=cfg.coder.temperature,
    )
    return llm_planner, llm_coder


def build_graph(
    cfg: AppConfig,
    tools,
    llm_planner: ChatVertexAI,
    llm_coder: ChatVertexAI,
    log: LogPacker,
):
    """Builds and compiles the LangGraph workflow."""

    architect_prompt = load_prompt(cfg.prompts.architect_path)
    engineer_prompt = load_prompt(cfg.prompts.engineer_path)

    llm_coder_with_tools = llm_coder.bind_tools(tools)
    tool_node = ToolNode(tools)

    def architect_node(state: AgentState):
        """Architect node: produces a step-by-step plan (no tool calls)."""

        messages = state["messages"]
        response = llm_planner.invoke(
            [SystemMessage(content=architect_prompt)] + messages
        )
        return {"messages": [response]}

    def engineer_node(state: AgentState):
        """Engineer node: executes plan via tools."""

        messages = state["messages"]
        response = llm_coder_with_tools.invoke(
            [SystemMessage(content=engineer_prompt)] + messages
        )
        return {"messages": [response]}

    def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        """ReAct loop routing: call tools if tool calls exist, otherwise end."""

        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return "__end__"

    workflow = StateGraph(AgentState)
    workflow.add_node("architect", architect_node)
    workflow.add_node("engineer", engineer_node)
    workflow.add_node("tools", tool_node)

    workflow.set_entry_point("architect")
    workflow.add_edge("architect", "engineer")
    workflow.add_conditional_edges("engineer", should_continue)
    workflow.add_edge("tools", "engineer")

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
            "planner_model": cfg.planner.model,
            "coder_model": cfg.coder.model,
            "prompts": {
                "architect": str(cfg.prompts.architect_path),
                "engineer": str(cfg.prompts.engineer_path),
            },
        },
    )

    tools = init_tools(cfg, log)
    llm_planner, llm_coder = init_llms(cfg, log)
    app = build_graph(cfg, tools, llm_planner, llm_coder, log)

    user_input = render_user_input(cfg)
    log.info("Starting multi-agent execution...")
    stream_pretty(app, user_input, log)
    log.info(f"Done. Check target directory: {cfg.target_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
