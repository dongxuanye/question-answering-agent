# test_serpapi.py（更新为 Client 类）
from serpapi import Client
from config import SERPAPI_CONFIG

def test_serpapi_search():
    print("测试 SerpAPI 搜索工具（Client 类）...")
    query = "手机支持无线充电吗？"
    try:
        client = Client(api_key=SERPAPI_CONFIG["api_key"])
        results = client.search({
            "q": query,
            "engine": SERPAPI_CONFIG["engine"],
            "hl": SERPAPI_CONFIG["hl"],
            "gl": SERPAPI_CONFIG["gl"],
        })
        print(f"搜索问题：{query}")
        print(f"搜索引擎：{SERPAPI_CONFIG['engine']}")
        organic_results = results.get("organic_results", [])
        if organic_results:
            snippet = organic_results[0].get("snippet", "无摘要")
            print(f"第一条结果摘要：{snippet}")
            return True
        else:
            print("未找到有机搜索结果")
            return False
    except Exception as e:
        print(f"搜索失败：{str(e)}")
        return False

if __name__ == "__main__":
    test_serpapi_search()