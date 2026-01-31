import os
from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

load_dotenv()
# ==========================================
# 1. 設定工作區
# ==========================================
WORKSPACE_ROOT = ".github"

toolkit = FileManagementToolkit(root_dir=WORKSPACE_ROOT)
tools = toolkit.get_tools()

# ==========================================
# 2. 設定 LLM (建議從環境變數讀取 API Key)
# ==========================================
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    google_api_key=os.getenv("GOOGLE_API_KEY", "YOUR_KEY_HERE"),
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
你是一個專業的程式碼重構專家。

你的任務是讀取舊專案的程式碼，進行現代化重構，並存入新資料夾。

**重要規則：**
1. **來源資料夾 (Source)**: `Racing-Car-Katas/`
   - 你只能從這裡 **讀取 (Read)** 檔案。
   - 絕對 **禁止** 修改或刪除這裡的檔案。

2. **目標資料夾 (Destination)**: `new_refactored_app/`
   - 你將重構後的程式碼 **寫入 (Write)** 這裡。
   - 如果該資料夾不存在，請先建立它。

3. **重構標準**:
   - 加入 Type Hints (Python) 或 TypeScript 類型。
   - 增加 Docstrings。
   - 將大型函式拆解為小函式。

**工作流程**:
1. 使用 `list_directory` 查看 `Racing-Car-Katas` 的結構。
2. 逐一讀取檔案內容。
3. 思考如何重構。
4. 將重構後的程式碼用 `write_file` 寫入 `new_refactored_app` 對應的路徑中。"""


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
    Refactor the Python code in the ./Python folder into Go.
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
    """

    # 這裡的範例保持原樣，但確保縮排為 4 隔
    events = app.stream({"messages": [("user", user_input)]}, stream_mode="values")

    for event in events:
        if "messages" in event:
            last_msg = event["messages"][-1]
            print(f"[{last_msg.type.upper()}]: {last_msg.content}")
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                print(f"   -> 呼叫工具: {last_msg.tool_calls}")
