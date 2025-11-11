from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI
from neo4j.exceptions import Neo4jError

from config import DEEPSEEK_CONFIG
from tools import search_tool,load_prompt, update_graph_tool
import re

# 加载提示词
answer_agent_prompt_text = load_prompt("answer_agent_prompt.txt")

# 初始化 LLM
llm = ChatOpenAI(
    model=DEEPSEEK_CONFIG["model_name"],
    api_key=DEEPSEEK_CONFIG["api_key"],
    base_url=DEEPSEEK_CONFIG["url"],
    temperature=DEEPSEEK_CONFIG["temperature"],
    max_tokens=DEEPSEEK_CONFIG["max-tokens"],
)


# process_question函数（传递核心实体给LLM）
def process_question(inputs: dict) -> dict:
    question = inputs.get("question", "")
    entity_label = inputs.get("entity_label", "")
    entity_name = inputs.get("entity_name", "")
    
    if not question:
        error_msg = "[答智能体-无输入问题]"
        print(error_msg)
        msg = HumanMessage(content=error_msg)
        return {"question": question, "agent_scratchpad": [msg]}
    
    search_result = search_tool(question)
    
    # 构建传递给LLM的消息（包含核心实体的完整信息）
    if entity_label and entity_name:
        msg_content = f"""核心实体Label：{entity_label}
核心实体名称：{entity_name}
数据库存储格式：(:{entity_label} {{name: '{entity_name}'}})
【重要】MATCH该实体时必须使用Label ":{entity_label}"，不能使用 ":{entity_name}"

问题：{question}

{search_result}"""
        print(f"📤 传递给LLM - Label: {entity_label}, 实体名: {entity_name}")
    else:
        msg_content = f"问题：{question}\n{search_result}"
    
    msg = HumanMessage(content=msg_content)
    return {"question": question, "agent_scratchpad": [msg]}

mua = "{{name: '实体名称'}}"
mub = "{{name: '实体A'}}"
muc = "{{name: '实体B'}}"
mue = "{{name: '口技'}}"
muf = "{{name: '走钢丝'}}"
mug = "{{name: '杂技艺术'}}"
muh = "{{name: '个人赛'}}"
mui = "{{name: '冬季两项'}}"
muj = "{{name: '冲刺赛'}}"
prompt = ChatPromptTemplate.from_messages([
    ("system", f"""
    {answer_agent_prompt_text}
    
    # 核心实体规则【最重要-牢记】
    用户输入包含"核心大类实体"，格式为"Label:实体名"（如"运动项目:杂技艺术"）：
    
    ⚠️ 关键理解：
    - 冒号前 = Label（数据库中的节点标签）
    - 冒号后 = 实体名（节点的name属性）
    - 数据库存储：(Label {mua})
    
    ✅ 正确用法示例：
    - 核心实体："运动项目:杂技艺术"
    - 数据库实际：(:运动项目 {mug})
    - MATCH时：MATCH (z:运动项目 {mug})  ← 用Label部分
    
    ❌ 严禁错误（会导致匹配失败）：
    - MATCH (z:杂技艺术 {mug})  ← 错！Label不能用实体名
    - 数据库中"杂技艺术"的Label是"运动项目"，不是"杂技艺术"！
    
    ⚠️ 再次强调：所有涉及核心实体的MATCH，必须用冒号前的Label！
    
    # Cypher生成规范（必须用```cypher代码块包裹）
    
    ## 一、执行顺序（不可颠倒）
    1. 约束：为所有Label生成唯一约束（格式：CREATE CONSTRAINT 标签_name_unique FOR (n:标签) REQUIRE n.name IS UNIQUE;）
       - 每个Label只需1条，不重复不遗漏
       - 约束已存在报错可忽略（系统会自动处理）
    2. 节点：MERGE所有实体节点（格式：MERGE (n:标签 {mua}) ON CREATE SET n.属性 = '值';）
       - 禁止使用CREATE，必须用MERGE
       - 属性补充用ON CREATE SET，避免覆盖已有数据
    3. 关系：创建实体间关系（格式：先MATCH节点，再MERGE关系）
    
    ## 二、节点规则
    - 核心实体处理【关键】：核心实体（格式"Label:实体名"）已在数据库中，不需要MERGE创建
    - 新实体创建：只为搜索结果中新出现的实体创建节点，必须包含name属性
    - Label选择【极其重要】：
      * Label必须是分类/类别名称，不能是实体名称本身
      * 正确：MERGE (p:比赛项目 {muh})  ← Label是"比赛项目"（类别）
      * 错误：MERGE (p:个人赛 {muh})    ← Label是"个人赛"（实体名）
      * 规则：多个同类实体应使用相同的Label（如"个人赛""冲刺赛"都用:比赛项目）
    - Label复用原则：如果实体名与核心实体相同，必须使用核心实体的Label
    - 属性补充：可补充type、description等属性，属性名用英文，值与搜索结果一致
    
    ## 三、关系规则【关键】
    - 命名：用中文动词短语（如"包含""拥有""属于""参与"）
    - 格式：必须先MATCH节点，再MERGE关系，禁止在MERGE中创建节点
    - 【极其重要】核心实体的Label使用：
      * 核心实体格式是"Label:实体名"，MATCH时只能用Label部分
      * 例：核心实体"运动项目:杂技艺术" → MATCH (z:运动项目 {mua})
      * 禁止：MATCH (z:杂技艺术 {mua})  ← 会匹配不到节点，关系创建失败
    - 【最重要】Label一致性：MATCH时使用的Label必须与MERGE创建节点时的Label完全一致
      ```
      正确示例：
      // 第二步：创建节点（使用:比赛项目标签）
      MERGE (p:比赛项目 {muh}) ON CREATE SET p.english_name = 'Individual';
      // 第三步：创建关系（使用相同的:比赛项目标签）
      MATCH (p:比赛项目 {muh})
      MATCH (w:运动项目 {mui})
      MERGE (w)-[r:包含]->(p);
      
      错误示例：
      MERGE (p:比赛项目 {muh});  ← 创建时用 :比赛项目
      MATCH (p:个人赛 {muh})     ← ❌ 错误！Label变成了 :个人赛
      // 这会导致MATCH找不到节点，关系创建失败（影响0行）
      ```
    - 强制要求：
      * 问题中有语义关联必须生成关系
      * 所有创建的节点必须建立关系，不允许孤立节点
      * 节点Label不能用实体名称，要用分类名称（如"比赛项目"而非"个人赛"）
    - 去重：同一对节点的同名关系用MERGE，不同场景的同名关系可用CREATE
    
    ## 四、灵活性要求
    - 标签、关系不必局限于特定领域，可根据问题场景动态拓展
    - 但必须严格遵循上述命名和格式规范
    
    ## 五、示例
    假设核心实体是"运动项目:冬季两项"，问题是"冬季两项包含哪些比赛项目？"，搜索结果显示有个人赛、冲刺赛等。
    
    ```cypher
    // 第一步：创建约束
    CREATE CONSTRAINT 运动项目_name_unique FOR (n:运动项目) REQUIRE n.name IS UNIQUE;
    CREATE CONSTRAINT 比赛项目_name_unique FOR (n:比赛项目) REQUIRE n.name IS UNIQUE;
    
    // 第二步：创建节点（核心实体已存在，只创建新实体）
    MERGE (p1:比赛项目 {muh}) ON CREATE SET p1.english_name = 'Individual';
    MERGE (p2:比赛项目 {muj}) ON CREATE SET p2.english_name = 'Sprint';
    
    // 第三步：创建关系（核心实体Label用"运动项目"，不是"冬季两项"！）
    MATCH (w:运动项目 {mui})
    MATCH (p1:比赛项目 {muh})
    MERGE (w)-[r1:包含]->(p1);
    
    MATCH (w:运动项目 {mui})
    MATCH (p2:比赛项目 {muj})
    MERGE (w)-[r2:包含]->(p2);
    ```
    
    【错误示例-禁止】：
    ```cypher
    // ❌ 错误：Label用实体名而非类别名
    MATCH (w:冬季两项 {mui})  ← 找不到节点！应该用 :运动项目
    ```
    """),
    ("user", "{question}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])
prompt.input_variables = ["question", "agent_scratchpad"]

llm_chain = prompt | llm

# 步骤3：串联流程链
answer_agent_chain = RunnableSequence(
    process_question,
    llm_chain,
    lambda x: {
        "llm_output": x.content.strip() if hasattr(x, "content") else str(x),
        "graph_update_result": update_graph_tool(extract_cypher(x.content.strip() if hasattr(x, "content") else str(x)))
    }
)


def extract_cypher(llm_output: str) -> str:
    """
    从LLM输出中提取Cypher代码块，保留注释和语句
    返回格式：完整的Cypher语句（包含注释），每条语句以分号结尾
    """
    if not llm_output:
        return ""
    
    # 正则表达式：匹配 ```cypher 开头，``` 结尾的内容（支持换行）
    cypher_block_pattern = r"```cypher\s*\n*(.*?)\n*```"
    match = re.search(cypher_block_pattern, llm_output, re.DOTALL)
    
    if match:
        cypher_content = match.group(1).strip()
        if cypher_content:
            # 保留所有内容（包括注释），只过滤空行
            valid_lines = []
            for line in cypher_content.split("\n"):
                stripped_line = line.strip()
                # 跳过纯空行
                if not stripped_line:
                    continue
                # 保留注释和所有Cypher语句
                valid_lines.append(stripped_line)
            return "\n".join(valid_lines)
    
    return ""



def generate_answer(ask_agent_output: dict) -> dict:
    """
    答智能体主函数：生成答案和Cypher语句，并分步执行
    返回结构化结果，供前端循环展示每一步的执行情况
    """
    result = {
        "status": "success",
        "data": {
            "question": ask_agent_output.get("question", ""),
            "answer": "",
            "cypher": "",
            "cypher_steps": [],  # 新增：CQL执行步骤详情
            "graph_update_summary": ""  # 新增：执行摘要
        },
        "error": ""
    }
    try:
        question = result["data"]["question"]
        entity_label = ask_agent_output.get("entity_label", "")
        entity_name = ask_agent_output.get("entity_name", "")

        # 向LLM传递指令
        chain_input = {
            "question": question,
            "entity_label": entity_label,
            "entity_name": entity_name
        }
        chain_result = answer_agent_chain.invoke(chain_input)
        llm_output = chain_result["llm_output"]
        print(f"📌 LLM原始输出：\n{llm_output}")

        # 提取答案
        answer_lines = [line.strip() for line in llm_output.split("\n") if line.strip().startswith("回复结果：")]
        answer = answer_lines[0].replace("回复结果：", "").strip() if answer_lines else "暂无相关信息"

        # 提取Cypher
        cypher = extract_cypher(llm_output)
        print(f"📌 提取后的Cypher：\n{cypher if cypher else '无'}")

        if cypher:
            result["data"]["cypher"] = cypher

            # 核心实体校验（如果有核心实体，检查Label是否在Cypher中）
            has_core_entity = (not entity_label) or (entity_label in cypher)
            
            if has_core_entity:
                # 执行Cypher并获取详细结果
                execution_result = update_graph_tool(cypher)
                
                result["data"]["graph_update_summary"] = execution_result.get("summary", "执行完成")
                result["data"]["cypher_steps"] = execution_result.get("details", [])
                
                # 根据执行结果调整状态
                if execution_result["status"] == "error":
                    result["status"] = "error"
                    result["error"] = execution_result.get("summary", "执行失败")
                elif execution_result["status"] == "partial":
                    result["status"] = "warning"
                    result["error"] = "部分语句执行失败，详见步骤详情"
                    
            else:
                result["status"] = "warning"
                result["error"] = f"核心实体Label「{entity_label}」未在Cypher中找到"
                result["data"]["graph_update_summary"] = "图谱更新失败：核心实体Label缺失"
                result["data"]["cypher_steps"] = []
        else:
            result["data"]["cypher"] = ""
            result["data"]["graph_update_summary"] = "无需要执行的Cypher语句"
            result["data"]["cypher_steps"] = []
            result["warning"] = "未从LLM输出中提取到有效Cypher"

        result["data"]["answer"] = answer
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"[答智能体执行失败] 原因：{str(e)}"
        print(result["error"])
        
    return result