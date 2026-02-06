from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_google_vertexai import ChatVertexAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

load_dotenv()
# ==========================================
# 1. 設定工作區
# ==========================================
WORKSPACE_ROOT = "."

toolkit = FileManagementToolkit(root_dir=WORKSPACE_ROOT)
tools = toolkit.get_tools()

# ==========================================
# 2. 設定 LLM (建議從環境變數讀取 API Key)
# ==========================================
llm = ChatVertexAI(
    model="gemini-2.5-pro",
    project="tsmchaker",
    location="global",
    temperature=0,
)

llm_with_tools = llm.bind_tools(tools)


# ==========================================
# 3. 定義 Graph State
# ==========================================
class AgentState(TypedDict):
    # 使用 list[Any] 或更精確的類型，Ruff 建議 Annotated 內的類型要明確
    messages: Annotated[list, add_messages]


# ==========================================
# 4. System Prompt
# ==========================================
SYSTEM_PROMPT = """
    You are a Senior Software Architect.

    You have access to tools.

    Before doing any planning tasks, you MUST first read and
    reason over the following three JSON files
    1) ./artifact/caa0ea0651474be18c2f4c265c32b9eb/
    depgraph/dep_graph_light_python.json
    2) ./artifact/caa0ea0651474be18c2f4c265c32b9eb/depgraph/
    dep_reverse_index_light_python.json
    3) ./artifact/caa0ea0651474be18c2f4c265c32b9eb/index/
    python_dir_index.json

    - First, use `list_directory` to confirm the file structure.
    - Use `read_file` to read the json file.



    Your tasks are:

    1) Analyze the refactoring requirements.
    2) Build dependency-aware stages (highly related modules in the same stage).
    3) Produce a complete refactoring plan in Markdown format.

    IMPORTANT FILE OUTPUT REQUIREMENT:
    - You MUST call the write_file tool.
    - You MUST save the plan to:
    ./spec/refactoring_plan.md
    - The file content MUST be valid Markdown.
    - You MUST write exactly ONE file.

    The Markdown file MUST include the following sections:
    1) Modification Structure
    2) Dependency Relationship Summary
    - include fan-in hotspots and example src + range evidence
    3) Staging Plan
    - Stage 0..N
    - files/modules
    - rationale
    - interface considerations
    - validation notes
    4) Modification Report
    - risks
    - mitigations
    - expected impacts
    - actionable next steps for the Engineer

    Rules:
    - Do NOT write any Go code.
    - Do NOT output the plan as chat text.
    - The plan MUST be written via write_file only.
    - After writing the file, respond with ONE sentence:
    "Engineer, please start the execution."
    ==================================================
    """


# ==========================================
# 5. 定義 Nodes
# ==========================================
def chatbot(state: AgentState) -> dict[str, list[BaseMessage]]:
    messages = state["messages"]

    # 優化邏輯：將 SystemMessage 插入
    if len(messages) == 1 and messages[0].type == "human":
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


tool_node = ToolNode(tools)

# ==========================================
# 6. 建構 Graph
# ==========================================
graph_builder = StateGraph(AgentState)
graph_builder.add_node("agent", chatbot)
graph_builder.add_node("tools", tool_node)

graph_builder.add_edge(START, "agent")


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END


graph_builder.add_conditional_edges("agent", should_continue)
graph_builder.add_edge("tools", "agent")

app = graph_builder.compile()
app.get_graph().print_ascii()
# ==========================================
# 7. 執行
# ==========================================
if __name__ == "__main__":
    print("--- 開始重構任務 ---")
    user_input = """
    First prompt:
    Refactor the Python code in the ./Racing-Car-Katas/Python folder into Go.
    First, analyze the project and generate the spec.md in
    the ./spec directory. This spec.md should detail the
    folder structure, a comprehensive to-do list, and other
    relevant specifications. The refactored Go code should
    be placed in ./refactor-golang. At the end of each
    refactoring phase, validate the changes by running unit
    tests or executing the project to check for
    errors/warnings. Follow standard Git flow for version
    control. Finally, update the spec/spec.md to-do list to
    reflect the completed tasks for that phase.
    Tell me the name of which file was converted to,
    and store the path of pair into
    ./spec/stage_result.md after each stage.
    Then do the next stage
    The spec.md MUST be generate whole process(every stages) once
    """

    # 這裡的範例保持原樣，但確保縮排為 4 隔
    events = app.stream({"messages": [("user", user_input)]}, stream_mode="values")

    for event in events:
        if "messages" in event:
            last_msg = event["messages"][-1]
            print(f"[{last_msg.type.upper()}]: {last_msg.content}")
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                print(f"   -> 呼叫工具: {last_msg.tool_calls}")
