import os
import re
from queue import Queue
from threading import Lock

from langchain_community.graphs import Neo4jGraph
from serpapi import Client

from config import NEO4J_CONFIG, SERPAPI_CONFIG  # 导入SerpAPI配置

# ===================== Neo4j连接池 =====================
class Neo4jConnectionPool:
    """Neo4j连接池，支持并发查询"""
    def __init__(self, config, pool_size=5):
        self.config = config
        self.pool_size = pool_size
        self.pool = Queue(maxsize=pool_size)
        self.lock = Lock()
        self._init_pool()
    
    def _init_pool(self):
        """初始化连接池"""
        print(f"[连接池] 初始化Neo4j连接池，大小: {self.pool_size}")
        for i in range(self.pool_size):
            conn = Neo4jGraph(
                url=self.config["url"],
                username=self.config["username"],
                password=self.config["password"],
                database=self.config["database"]
            )
            self.pool.put(conn)
            print(f"[连接池] 创建连接 {i+1}/{self.pool_size}")
    
    def get_connection(self):
        """从连接池获取连接"""
        conn = self.pool.get()
        print(f"[连接池] 获取连接，剩余: {self.pool.qsize()}")
        return conn
    
    def release_connection(self, conn):
        """释放连接回连接池"""
        self.pool.put(conn)
        print(f"[连接池] 释放连接，剩余: {self.pool.qsize()}")

# 初始化连接池
neo4j_pool = Neo4jConnectionPool(NEO4J_CONFIG, pool_size=3)

# 初始化默认Neo4j连接（用于工作流主线程）
graph = neo4j_pool.get_connection()

# 路径处理函数
def get_project_root():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return current_dir


def load_prompt(file_name: str) -> str:
    """加载纯文本提示词，无变量"""
    project_root = get_project_root()
    file_path = os.path.join(project_root, "prompts", file_name)
    print(f"正在加载智能体提示词文件：{file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        error_msg = f"[智能体-提示词加载失败] 原因：{str(e)}"
        print(error_msg)
        return error_msg

# 工具2：图谱更新工具
def update_graph_tool(cypher: str) -> dict:
    """
    图谱更新工具：分步执行Cypher并返回结构化结果
    返回格式：{"status": "success/error", "summary": "摘要", "details": [...]}
    """
    try:
        if not cypher.strip():
            return {
                "status": "skipped",
                "summary": "无需要执行的Cypher",
                "details": []
            }
        
        # 调用增强的执行函数
        result = execute_neo4j_query(cypher)
        
        if result["status"] == "success":
            # 统计执行情况
            success_count = len([r for r in result["results"] if r["status"] == "success"])
            error_count = len([r for r in result["results"] if r["status"] == "error"])
            
            summary = f"执行完成：成功 {success_count} 条，失败 {error_count} 条"
            
            return {
                "status": "success" if error_count == 0 else "partial",
                "summary": summary,
                "total": result["total_statements"],
                "details": result["results"]
            }
        else:
            return {
                "status": "error",
                "summary": result.get("message", "执行失败"),
                "details": result.get("results", [])
            }
            
    except Exception as e:
        error_msg = f"[图谱更新失败] 原因：{str(e)}"
        print(error_msg)
        return {
            "status": "error",
            "summary": error_msg,
            "details": []
        }

# def get_graph_data():
#     """工具a：查询知识图谱数据（供前端展示）"""
#     try:
#         nodes_query = "MATCH (n) RETURN id(n) as id, labels(n) as labels, properties(n) as properties"
#         relationships_query = "MATCH (n)-[r]->(m) RETURN id(n) as source, id(m) as target, type(r) as type"
#
#         nodes = graph.query(nodes_query)
#         relationships = graph.query(relationships_query)
#
#         # 格式化返回数据（适配vis-network）
#         formatted_nodes = [
#             {
#                 "id": n["id"],
#                 "label": n["labels"][0] if n["labels"] else "未知实体",
#                 "title": n["properties"].get("name", str(n["id"]))
#             }
#             for n in nodes
#         ]
#         formatted_edges = [
#             {
#                 "from": r["source"],
#                 "to": r["target"],
#                 "label": r["type"]
#             }
#             for r in relationships
#         ]
#         return {"nodes": formatted_nodes, "edges": formatted_edges}
#     except Exception as e:
#         return {"error": f"图谱查询失败: {str(e)}"}, 500
def get_graph_data():
    """工具a：查询知识图谱数据（适配前端要求格式）"""
    query_graph = None
    try:
        # 从连接池获取连接，避免与工作流冲突导致阻塞
        query_graph = neo4j_pool.get_connection()
        
        # 优化节点查询：同时获取 id、labels、properties（保持原有查询，后续格式化调整）
        nodes_query = "MATCH (n) RETURN id(n) as id, labels(n) as labels, properties(n) as properties"
        # 关系查询补充 id(r)，用于 edge 的唯一标识
        relationships_query = "MATCH (n)-[r]->(m) RETURN id(r) as edge_id, id(n) as source, id(m) as target, type(r) as type"

        nodes = query_graph.query(nodes_query)  # 使用连接池中的连接查询
        relationships = query_graph.query(relationships_query)

        # 格式化节点：适配前端要求的字段
        formatted_nodes = [
            {
                "id": f"node_{n['id']}",  # 统一前缀，确保与 edge 的 from/to 对应
                "label": n["properties"].get("name", n["labels"][0]) if n["labels"] else "未知实体",
                "type": n["labels"][0] if n["labels"] else "未知类型",  # type 字段复用第一个 label
                "properties": n["properties"]  # 保留完整属性（空对象时返回 {}）
            }
            for n in nodes
        ]

        # 格式化关系：适配前端要求的字段
        formatted_edges = [
            {
                "id": f"edge_{r['edge_id']}",  # 关系唯一标识（加前缀区分节点 id）
                "from": f"node_{r['source']}",  # 对应节点的 id（带前缀）
                "to": f"node_{r['target']}",    # 对应节点的 id（带前缀）
                "label": r["type"],             # 关系标签复用 type
                "type": r["type"]               # 关系类型字段
            }
            for r in relationships
        ]

        return {"nodes": formatted_nodes, "edges": formatted_edges}
    except Exception as e:
        # 抛出异常，由上层接口统一处理错误响应
        raise Exception(str(e))
    finally:
        # 确保连接释放回连接池
        if query_graph is not None:
            neo4j_pool.release_connection(query_graph)


def get_least_relationship_entity():
    """获取 Neo4j 中关系最少的实体（返回实体名称和Label）"""
    try:
        # 查询实体名称和Label
        cypher = """
        MATCH (n)
        OPTIONAL MATCH (n)-[r]-()
        WITH n, count(r) AS relationCount
        ORDER BY relationCount ASC, id(n) ASC
        LIMIT 1
        RETURN n.name AS entity_name, labels(n) AS entity_labels
        """
        print(f"执行实体查询Cypher：\n{cypher}")
        result = graph.query(cypher)

        # 详细日志：输出原始查询结果
        print(f"Cypher查询原始结果：{result}")

        # 结果处理
        if not result or len(result) == 0:
            print("❌ 未查询到有效实体：数据库中无实体")
            return {"name": "", "label": ""}

        entity_info = result[0]
        entity_name = entity_info.get("entity_name", "").strip()
        entity_labels = entity_info.get("entity_labels", [])
        
        # 获取第一个Label（通常一个节点只有一个Label）
        entity_label = entity_labels[0] if entity_labels else ""

        if not entity_name:
            print("❌ 查询到实体，但名称为空")
            return {"name": "", "label": ""}

        print(f"✅ 查询到实体：{entity_name}，Label：{entity_label}")
        return {"name": entity_name, "label": entity_label}
    except Exception as e:
        print(f"❌ 实体查询失败：{str(e)}")
        return {"name": "", "label": ""}



# 搜索结果缓存（节约API，保留搜索工具）
SEARCH_CACHE = {}
# 工具1：保留 search_tool（带缓存，正常调用API）
def search_tool(query: str) -> str:
    # return "搜索结果：一：用无线充电器测试 这是最简单直接的方法，把手机放在无线充电器上，如果显示充电，就表示具备无线充电功能，反之则不支持。 这样测试是因为目前市面上的无 ........."
    # 缓存命中直接返回
    if query in SEARCH_CACHE:
        print(f"✅ 命中搜索缓存（节约API）：{query}")
        return SEARCH_CACHE[query]

    # 缓存未命中，调用SerpAPI
    try:
        api_key = SERPAPI_CONFIG.get("api_key")
        if not api_key:
            raise ValueError("SERPAPI api_key 未配置")

        client = Client(api_key=api_key)
        results = client.search({
            "q": query,
            "engine": SERPAPI_CONFIG.get("engine", "baidu"),
            "hl": "zh-CN",
            "gl": "cn"
        })

        organic_results = results.get("organic_results", [])
        if organic_results:
            snippet = organic_results[0].get("snippet", "") or organic_results[0].get("title", "")
            result = f"搜索结果：{snippet.strip()}"
        else:
            result = "搜索结果：未找到相关答案"

        SEARCH_CACHE[query] = result
        print(f"✅ 搜索API调用成功（已缓存）：{query}")
        return result
    except Exception as e:
        error_msg = f"[搜索工具失败] 原因：{str(e)}"
        print(error_msg)
        return error_msg


def execute_neo4j_query(cypher: str):
    """
    工具d：分步执行Cypher语句（供答智能体）
    支持三步格式：约束 → 节点 → 关系
    返回：结构化的执行结果列表
    """
    try:
        # 基础安全校验：禁止危险操作
        dangerous_patterns = r"\bDROP\b|\bDELETE\b(?!\s+constraint)|\bREMOVE\b"
        if re.search(dangerous_patterns, cypher, re.IGNORECASE):
            raise ValueError("禁止执行删除、清空等危险操作")

        # 解析Cypher：按分号分割语句，过滤注释行
        statements = []
        current_statement = []
        
        for line in cypher.split('\n'):
            line = line.strip()
            
            # 保留纯注释行作为分组标记
            if line.startswith('//'):
                # 如果有累积的语句，先保存
                if current_statement:
                    statements.append('\n'.join(current_statement))
                    current_statement = []
                # 保存注释作为标记
                statements.append(line)
                continue
            
            # 跳过空行
            if not line:
                continue
            
            # 累积语句内容
            current_statement.append(line)
            
            # 遇到分号，说明一条语句结束
            if line.endswith(';'):
                statements.append('\n'.join(current_statement))
                current_statement = []
        
        # 处理最后可能没有分号的语句
        if current_statement:
            statements.append('\n'.join(current_statement))
        
        # 执行每条语句并记录结果
        execution_results = []
        step_counter = 0  # 实际执行的步骤计数器
        for i, stmt in enumerate(statements, 1):
            # 跳过纯注释（不添加到结果中，因为前端不需要显示注释步骤）
            if stmt.startswith('//'):
                continue
            
            step_counter += 1  # 只对实际执行的语句计数
            
            try:
                # 判断语句类型（优先级：约束 > 关系 > 节点）
                stmt_upper = stmt.upper()
                if 'CREATE CONSTRAINT' in stmt_upper:
                    stmt_type = "constraint"
                elif 'MATCH' in stmt_upper and 'MERGE' in stmt_upper and ('-[' in stmt or '->' in stmt):
                    stmt_type = "relationship"  # MATCH...MERGE关系模式
                elif 'MERGE' in stmt_upper and ('-[' in stmt or '->' in stmt):
                    stmt_type = "relationship"  # 直接MERGE关系
                elif 'MERGE' in stmt_upper:
                    stmt_type = "node"
                elif 'MATCH' in stmt_upper:
                    stmt_type = "match"
                else:
                    stmt_type = "other"
                
                # 执行语句
                result = graph.query(stmt)
                
                execution_results.append({
                    "step": step_counter,
                    "cypher": stmt,
                    "status": "success",
                    "result": f"✅ 执行成功 (影响 {len(result) if result else 0} 行)",
                    "type": stmt_type,
                    "affected_rows": len(result) if result else 0
                })
            except Exception as stmt_error:
                error_msg = str(stmt_error)
                
                # 区分不同类型的错误
                if "equivalent constraint already exists" in error_msg.lower() or \
                   ("already exists" in error_msg.lower() and "constraint" in stmt_upper and "CREATE CONSTRAINT" in stmt_upper):
                    # 约束已存在 - 视为成功（因为约束目标已达成）
                    execution_results.append({
                        "step": step_counter,
                        "cypher": stmt,
                        "status": "success",
                        "result": "⚠️ 约束已存在（跳过创建，继续执行）",
                        "type": "constraint"
                    })
                elif "ConstraintValidationFailed" in error_msg:
                    # 约束验证失败（节点/关系冲突）
                    execution_results.append({
                        "step": step_counter,
                        "cypher": stmt,
                        "status": "error",
                        "error": f"❌ 约束验证失败：节点可能已存在但属性不匹配，或关系创建冲突。{error_msg[:150]}",
                        "type": stmt_type if 'stmt_type' in locals() else "unknown"
                    })
                else:
                    # 其他错误
                    execution_results.append({
                        "step": step_counter,
                        "cypher": stmt,
                        "status": "error",
                        "error": f"❌ 执行失败: {error_msg}",
                        "type": stmt_type if 'stmt_type' in locals() else "unknown"
                    })
        
        return {
            "status": "success",
            "total_statements": len([s for s in statements if not s.startswith('//')]),
            "results": execution_results
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ Cypher解析/执行失败: {str(e)}",
            "results": []
        }