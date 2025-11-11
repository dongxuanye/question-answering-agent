# 数据库配置
NEO4J_CONFIG = {
    "url": "bolt://172.18.57.69:7687",
    "username": "neo4j",
    "password": "learning123",
    "database": "aip-graph"
}

# LLM配置（Deepseek）
DEEPSEEK_CONFIG = {
    "model_name": "deepseek-chat",
    "api_key": "xx",  # 替换为你的Deepseek API密钥
    "temperature": 0.1,
    "url": "https://api.deepseek.com",
    "max-tokens": 8192
}

# 工作流配置
WORKFLOW_CONFIG = {
    "max_ask_count": 1,  # 答智能体最多触发2次ask
    "loop_delay": 15      # 智能体循环延迟（秒）
}

# 搜索工具配置（SerpAPI）
SERPAPI_CONFIG = {
    # "url": "https://google.serper.dev/search",  # SerpAPI请求URL（核心新增）
    "api_key": "xxx",
    "engine": "google",
    "timeout": 10,
    "max_result_length": 500,
    "hl": "zh-CN",
    "gl": "cn"
}