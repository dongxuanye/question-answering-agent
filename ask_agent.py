import os

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSequence
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from config import DEEPSEEK_CONFIG
from tools import get_least_relationship_entity,load_prompt

# 2. 直接加载整合后的提示词（无需再拼接enhanced_prompt_text）
ask_agent_prompt_text = load_prompt("ask_agent_prompt.txt")

# 3. 构建提示词模板：直接使用加载的文本，无需额外添加内容
prompt = ChatPromptTemplate.from_messages([
    ("system", ask_agent_prompt_text),  # 直接用文件中的完整指令
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])


# 初始化 LLM（不变）
llm = ChatOpenAI(
    model=DEEPSEEK_CONFIG["model_name"],
    api_key=DEEPSEEK_CONFIG["api_key"],
    base_url=DEEPSEEK_CONFIG["url"],
    temperature=DEEPSEEK_CONFIG["temperature"],
    max_tokens=DEEPSEEK_CONFIG["max-tokens"],
)


# 步骤1：修改工具调用函数（用 HumanMessage 包装结果，无需 tool_call_id）
def call_least_entity_tool(inputs: dict) -> dict:
    try:
        entity_info = get_least_relationship_entity()
        entity_name = entity_info.get("name", "") if isinstance(entity_info, dict) else ""
        entity_label = entity_info.get("label", "") if isinstance(entity_info, dict) else ""
        
        has_valid_entity = bool(entity_name)
        
        if has_valid_entity:
            log_msg = f"✅ 工具调用结果：获取到实体「{entity_name}」，Label：{entity_label}"
            tool_content = f"工具 GetLeastRelationshipEntity 返回的实体：{entity_name}（Label：{entity_label}）"
        else:
            log_msg = "❌ 工具调用结果：无可用实体"
            tool_content = "工具 GetLeastRelationshipEntity 返回空（无可用实体）"
        
        print(log_msg)
        tool_result_msg = HumanMessage(content=tool_content)

        return {
            "input": inputs["input"],
            "agent_scratchpad": [tool_result_msg],
            "raw_entity": f"{entity_label}:{entity_name}" if entity_label and entity_name else entity_name,
            "has_valid_entity": has_valid_entity
        }
    except Exception as e:
        error_msg = f"[工具调用失败] 原因：{str(e)}"
        print(error_msg)
        tool_result_msg = HumanMessage(content=error_msg)
        return {
            "input": inputs["input"],
            "agent_scratchpad": [tool_result_msg],
            "raw_entity": "",
            "has_valid_entity": False  # 异常时同样标记为"无有效实体"
        }

llm_chain = prompt | llm

# 完整流程链（不变）
ask_agent_chain = RunnableSequence(
    call_least_entity_tool,
    llm_chain
)


def generate_question() -> dict:
    result = {
        "status": "success",
        "data": {
            "question": "",
            "entity_label": "",
            "entity_name": ""
        },
        "error": ""
    }
    try:
        chain_input = {"input": ""}
        # 1. 先调用工具，判断是否有有效实体
        tool_result = call_least_entity_tool(chain_input)
        if not tool_result["has_valid_entity"]:
            # 无有效实体 → 直接返回error状态，中断后续流程
            result["status"] = "error"
            result["error"] = "问智能体执行失败：未从Neo4j数据库中查询到有效实体，无法生成问题"
            result["data"] = {}  # 无有效数据，清空data
            print(result["error"])
            return result

        # 2. 有有效实体 → 继续生成问题
        chain_result = ask_agent_chain.invoke(tool_result)
        raw_output = chain_result.content.strip() if hasattr(chain_result, "content") else str(chain_result)

        # 从工具结果中提取Label和实体名
        entity_info = get_least_relationship_entity()
        entity_label = entity_info.get("label", "") if isinstance(entity_info, dict) else ""
        entity_name = entity_info.get("name", "") if isinstance(entity_info, dict) else ""

        if "@@@" in raw_output:
            question, _ = raw_output.split("@@@", 1)
            question = question.strip()

            if question and len(question) <= 50 and question.endswith("？"):
                result["data"]["question"] = question
                result["data"]["entity_label"] = entity_label
                result["data"]["entity_name"] = entity_name
                print(f"✅ 问题：{question}")
                print(f"✅ 实体Label：{entity_label}")
                print(f"✅ 实体名称：{entity_name}")
            else:
                result["status"] = "warning"
                result["error"] = "生成的问题长度超标/非疑问句/格式错误"
                result["data"]["question"] = raw_output
                result["data"]["entity_label"] = entity_label
                result["data"]["entity_name"] = entity_name
        else:
            result["status"] = "warning"
            result["error"] = "输出格式不符合「问题@@@核心实体」要求，已用工具原始结果兜底"
            result["data"]["question"] = raw_output
            result["data"]["entity_label"] = entity_label
            result["data"]["entity_name"] = entity_name

    except Exception as e:
        result["status"] = "error"
        result["error"] = f"[问智能体执行失败] 原因：{str(e)}"
        print(result["error"])
    return result