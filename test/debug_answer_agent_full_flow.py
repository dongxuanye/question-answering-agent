# 答智能体专属调试脚本：模拟完整流程
from answer_agent import generate_answer, search_tool, extract_cypher
from tools import graph

def debug_answer_agent_full_flow():
    print("="*80)
    print("【完整流程】答智能体（接收问题→搜索→生成答案+Cypher→更新图谱）")
    print("="*80)

    # 1. 模拟接收问智能体问题
    test_question = {'question': '电脑的品牌有哪些？', 'low_relation_entity': '电脑'}
    print(f"\n1. 模拟接收问智能体问题：{test_question}")

    # 2. 验证搜索工具
    print("\n2. 验证搜索工具调用...")
    try:
        search_result = search_tool(test_question.get("question",""))
        # search_result = "搜索结果：一：用无线充电器测试 这是最简单直接的方法，把手机放在无线充电器上，如果显示充电，就表示具备无线充电功能，反之则不支持。 这样测试是因为目前市面上的无 ......"
        print(f"✅ 搜索工具返回：{search_result[:100]}...")
    except Exception as e:
        print(f"❌ 搜索工具调用失败：{e}")
        print("💡 排查：SERPAPI api_key 配置、余额、网络")

    # 3. 执行完整流程
    print("\n3. 答智能体完整流程执行...")
    result = generate_answer(test_question)

    # 4. 解析结果
    if result["status"] == "success":
        print(f"\n✅ 执行成功！")
        print(f"问题：{result['data']['question']}")
        print(f"答案：{result['data']['answer']}")
        print(f"Cypher语句：{result['data']['cypher']}")
        print(f"图谱更新结果：{result['data']['graph_update_result']}")

        # 验证图谱更新
        print("\n4. 验证 Neo4j 图谱更新...")
        try:
            entity_count = graph.query("MATCH (n) RETURN count(n) AS cnt")[0]["cnt"]
            print(f"✅ 图谱当前实体总数：{entity_count}")
        except Exception as e:
            print(f"❌ 图谱查询失败：{e}")
    elif result["status"] == "warning":
        print(f"\n⚠️  业务警告：{result['error']}")
        print(f"原始输出：{result['data']['answer']}")
    else:
        print(f"\n❌ 执行失败：{result['error']}")

    # 5. 验证Cypher提取逻辑
    print("\n5. 验证Cypher提取逻辑...")
    test_llm_output = """
    一、回复结果：是，主流中高端手机大多支持无线充电功能。
    二、执行SQL：MERGE (p:产品 {name: '手机'}) SET p.支持无线充电 = true;
    """
    extracted_cypher = extract_cypher(test_llm_output)
    print(f"测试LLM输出：{test_llm_output.strip()}")
    print(f"提取的Cypher：{extracted_cypher}")
    print("✅ Cypher提取成功" if extracted_cypher else "❌ Cypher提取失败")

    print("\n" + "="*80)
    print("【完整流程】答智能体调试结束")
    print("="*80)

if __name__ == "__main__":
    debug_answer_agent_full_flow()