import os
from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_google_vertexai import ChatVertexAI

# from langchain_google_vertexai import ChatAnthropicVertex
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# 載入環境變數
load_dotenv()

# ==========================================
# 1. 設定工作區與工具
# ==========================================
# 設定 root_dir="." 讓 Agent 可以讀取專案內的所有資料夾
# 包含來源 (Racing-Car-Katas) 與目標 (refactor-golang)
WORKING_DIRECTORY = "."

print(f"📂 初始化檔案系統工具，根目錄: {os.path.abspath(WORKING_DIRECTORY)}")
toolkit = FileManagementToolkit(root_dir=WORKING_DIRECTORY)
tools = toolkit.get_tools()

# ==========================================
# 2. 初始化雙模型 (Dual LLM)
# ==========================================

# 🧠 架構師：使用 Claude 3.5 Sonnet
# 專長：邏輯分析、架構設計、指令遵循
print("🧠 初始化架構師 (Planner) - 使用 Claude 3.5 Sonnet...")
llm_planner = ChatVertexAI(
    model="qwen/qwen3-next-80b-a3b-thinking-maas",
    project="tsmchaker",
    location="global",
    temperature=0,
)

# 👨‍💻 工程師：使用 Google Gemini 1.5 Pro
# 專長：長文本處理 (讀大量Code)、執行工具、寫程式
print("👨‍💻 初始化工程師 (Coder) - 使用 Gemini 1.5 Pro...")
llm_coder = ChatVertexAI(
    model="gemini-2.5-pro", project="tsmchaker", location="global", temperature=0
)

# 綁定工具：只有工程師需要「手」(Tools) 來寫檔案
llm_coder_with_tools = llm_coder.bind_tools(tools)


# ==========================================
# 3. 定義 Graph State
# ==========================================
class AgentState(TypedDict):
    # 這裡會儲存所有的對話紀錄，讓工程師能看到架構師的計畫
    messages: Annotated[list[BaseMessage], add_messages]


# ==========================================
# 4. 定義節點 (Nodes)
# ==========================================


def architect_node(state: AgentState):
    """
    [節點] 架構師
    職責：讀取使用者需求 -> 規劃重構步驟 -> 傳給工程師
    注意：架構師不會執行 write_file，只負責出嘴 (Plan)。
    """
    messages = state["messages"]

    # 架構師專屬 Prompt
    system_prompt = SystemMessage(
        content="""
    You are a Senior Software Architect.

    Your tasks are:
    1. Analyze the user's refactoring requirements.
    2. Provide the Engineer with a concrete **Step-by-step Plan**.
    3. Your plan MUST include instructions to:
    - First, use `list_directory` to confirm the file structure.
    - Use `read_file` to read the legacy Python source code.
    - Design the target Go project structure (e.g., `cmd`, `internal`, `go.mod`).

    **Important Constraints:**
    - You do **NOT** need to write the complete Go code;
    that is the Engineer's job.
    - You **CANNOT** call tools (Function Calling);
    you must output the plan strictly as text.
    - Your final sentence must be: "Engineer, please start the execution."
    """
    )

    # 將 System Prompt 放在對話最前面
    response = llm_planner.invoke([system_prompt] + messages)
    return {"messages": [response]}


def engineer_node(state: AgentState):
    """
    [節點] 工程師
    職責：看架構師的計畫 -> 呼叫工具 (Read/Write) ->回報結果
    """
    messages = state["messages"]

    # 工程師專屬 Prompt
    system_prompt = SystemMessage(
        content="""
    You are an Expert Implementation Engineer.

    Your goal is to translate the Architect's
    high-level plan into executable code.

    **Primary Actions:**
    1. **Context Awareness:** Use `list_directory`
    to map out the environment.
    2. **Source Analysis:** Use `read_file` to extract
    logic from the legacy codebase.
    3. **Code Generation:** Use `write_file` to
    construct the new application.

    **Critical Rules for Hackathon Context:**
    1. **Isolation:** You are strictly forbidden from modifying
    any files in the source directory.
    2. **Completeness:** The target directory must contain
    a fully functional project structure. This includes:
    - Main application logic.
    - Dependency files (e.g., `go.mod` for Go, `pom.xml` for Java).
    - Necessary subdirectories (e.g., `cmd`, `internal`, `pkg`).
    3. **Communication:** After each `write_file` operation,
    confirm the action with a single sentence
    (e.g., "Created cmd/main.go successfully.").
    """
    )

    # """
    # 你是一個資深的 Golang 工程師 (Engineer)。

    # 你的任務是：
    # 1. 仔細閱讀上方架構師 (Architect) 的計畫。
    # 2. 使用工具 (Tools) 實際執行任務：
    #    - 呼叫 `list_directory` 查看環境。
    #    - 呼叫 `read_file` 讀取舊程式碼。
    #    - 呼叫 `write_file` 建立新資料夾與 Go 程式碼。

    # 規則：
    # - 來源資料夾 (Source): `./Racing-Car-Katas/Python` (唯讀)
    # - 目標資料夾 (Target): `./refactor-golang` (寫入)
    # - 如果需要初始化 Go module，請直接寫入 `go.mod` 檔案。
    # - 每次完成一個階段 (例如寫完一個檔案)，請簡短回報。
    # """

    # 傳入完整的歷史訊息 (包含 User 的需求 + Architect 的計畫)
    response = llm_coder_with_tools.invoke([system_prompt] + messages)
    return {"messages": [response]}


# 建立工具節點 (LangGraph 內建)
tool_node = ToolNode(tools)

# ==========================================
# 5. 建構 Graph (流程圖)
# ==========================================
workflow = StateGraph(AgentState)

# (1) 加入節點
workflow.add_node("architect", architect_node)
workflow.add_node("engineer", engineer_node)
workflow.add_node("tools", tool_node)

# (2) 設定流程
# Start -> 架構師規劃
workflow.set_entry_point("architect")

# 架構師 -> 工程師執行
workflow.add_edge("architect", "engineer")


# (3) 設定工程師的迴圈 (ReAct Loop)
# 工程師講完話後，檢查是否有 Tool Calls
def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]

    # 如果工程師想要呼叫工具
    if last_message.tool_calls:
        return "tools"

    # 如果工程師沒呼叫工具 (代表任務完成或需要人類確認)
    return "__end__"


workflow.add_conditional_edges("engineer", should_continue)

# 工具執行完畢 -> 回到工程師 (讓它繼續做下一步)
workflow.add_edge("tools", "engineer")

# (4) 編譯圖形
app = workflow.compile()

# ==========================================
# 6. 執行主程式
# ==========================================
if __name__ == "__main__":
    print("\n🚀 雙腦協作 Agent 啟動中...\n")
    print("---------------------------------------")

    # 模擬使用者指令
    user_input = (
        "Refactor the codebase located in ."
        "/Racing-Car-Katas/Python into Golang."
        " Output the new code to the ./refactor-golang directory. "
        "Requirement: Preserve the exact business "
        "logic and include meaningful comments."
    )

    # 開始執行 Graph
    inputs = {"messages": [HumanMessage(content=user_input)]}

    # stream_mode="values" 會即時回傳每一步的狀態更新
    for event in app.stream(inputs, stream_mode="values"):
        last_msg = event["messages"][-1]

        # 漂亮的輸出格式化
        if last_msg.type == "ai":
            # 判斷是誰在說話 (透過 metadata 或內容判斷，這裡簡單用 tool_calls 判斷)
            # 架構師是不會呼叫 tool 的 (因為我們沒綁定 tool 給它)
            if "Claude" in str(last_msg.response_metadata.get("model_name", "")):
                role = "🧠 架構師 (Claude)"
                color = "\033[95m"  # 紫色
            else:
                role = "👨‍💻 工程師 (Gemini)"
                color = "\033[94m"  # 藍色

            reset = "\033[0m"

            print(f"\n{color}[{role}]:{reset}")
            print(f"{last_msg.content}")

            if last_msg.tool_calls:
                print(
                    f"\033[93m   🛠️\
                    呼叫工具: {[t['name'] for t in last_msg.tool_calls]}\033[0m"
                )

        elif last_msg.type == "tool":
            print(f"\033[92m   ✅ 工具回傳 (長度: {len(str(last_msg.content))})\033[0m")

    print("\n🏁 任務結束。請檢查 `./refactor-golang` 資料夾。")
