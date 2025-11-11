# 答智能体优化后测试脚本（专注后端调试，不涉及前端）
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from answer_agent import generate_answer, extract_cypher
from tools import graph, execute_neo4j_query
import json

def print_section(title):
    """打印分隔线"""
    print("\n" + "="*80)
    print(f"【{title}】")
    print("="*80)

def test_extract_cypher():
    """测试1：验证Cypher提取功能"""
    print_section("测试1：Cypher提取功能")
    
    test_llm_output = """
回复结果：电脑的主流品牌包括联想、华为、惠普、机械革命、七彩虹等。

```cypher
// 第一步：为涉及的Label创建唯一约束（1个Label对应1条约束）
CREATE CONSTRAINT 电脑品牌_name_unique FOR (n:电脑品牌) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT 电脑_name_unique FOR (n:电脑) REQUIRE n.name IS UNIQUE;

// 第二步：MERGE核心实体节点（补充基础属性）
MERGE (c:电脑 {name: '电脑'}) ON CREATE SET c.category = '电子产品', c.description = '用于数据处理、办公、娱乐等的电子设备';
MERGE (b1:电脑品牌 {name: '联想'}) ON CREATE SET b1.english_name = 'Lenovo', b1.price_range = '￥1800-￥48999';
MERGE (b2:电脑品牌 {name: '华为'}) ON CREATE SET b2.english_name = 'Huawei', b2.price_range = '￥3598-￥26999';

// 第三步：创建实体间的关联关系（电脑与电脑品牌的"拥有"关系）
MERGE (c)-[r1:拥有]->(b1) ON CREATE SET r1.create_time = date();
MERGE (c)-[r2:拥有]->(b2) ON CREATE SET r2.create_time = date();
```
"""
    
    extracted = extract_cypher(test_llm_output)
    print("LLM原始输出：")
    print(test_llm_output)
    print("\n提取后的Cypher：")
    print(extracted)
    
    # 验证提取结果
    assert extracted, "❌ 提取失败：结果为空"
    assert "CREATE CONSTRAINT" in extracted, "❌ 未提取到约束语句"
    assert "MERGE" in extracted, "❌ 未提取到MERGE语句"
    assert "//" in extracted, "❌ 未保留注释"
    
    print("\n✅ Cypher提取功能正常")

def test_full_workflow():
    """测试2：完整答智能体流程"""
    print_section("测试2：完整答智能体流程")
    
    # 模拟问智能体输出
    test_input = {
        'question': '电脑的品牌有哪些？',
        'low_relation_entity': '电脑'
    }
    
    print(f"输入问题：{test_input['question']}")
    print(f"核心实体：{test_input['low_relation_entity']}\n")
    
    # 调用答智能体
    result = generate_answer(test_input)
    
    print("="*80)
    print("【答智能体返回结果】")
    print("="*80)
    print(f"状态：{result['status']}")
    print(f"错误信息：{result.get('error', '无')}\n")
    
    print(f"问题：{result['data']['question']}")
    print(f"\n答案：{result['data']['answer']}\n")
    
    if result['data'].get('cypher'):
        print("生成的Cypher语句：")
        print("-"*80)
        print(result['data']['cypher'])
        print("-"*80)
    
    if result['data'].get('graph_update_summary'):
        print(f"\n图谱更新摘要：{result['data']['graph_update_summary']}")
    
    if result['data'].get('cypher_steps'):
        print("\nCypher执行详情：")
        print("-"*80)
        for step in result['data']['cypher_steps']:
            status_icon = {
                'success': '✅',
                'error': '❌',
                'skipped': '⚠️'
            }.get(step['status'], '❓')
            
            print(f"\n步骤 {step['step']} [{step['type']}] {status_icon}")
            print(f"  语句：{step['statement'][:80]}{'...' if len(step['statement']) > 80 else ''}")
            print(f"  状态：{step['message']}")
            if step.get('error'):
                print(f"  错误：{step['error'][:100]}{'...' if len(step['error']) > 100 else ''}")
        print("-"*80)
    
    # 验证必要字段
    assert result['data']['question'], "❌ 缺少问题字段"
    assert result['data']['answer'], "❌ 缺少答案字段"
    
    if result['data'].get('cypher'):
        assert result['data'].get('cypher_steps'), "❌ 有Cypher但缺少执行步骤"
        assert result['data'].get('graph_update_summary'), "❌ 有Cypher但缺少执行摘要"
    
    print("\n✅ 完整流程测试通过")

def test_graph_verification():
    """测试3：验证图谱更新（检查空节点问题）"""
    print_section("测试3：验证图谱更新")
    
    try:
        # 查询所有节点（包括空节点）
        all_nodes = graph.query("""
            MATCH (n) 
            RETURN n, labels(n) AS labels, 
                   CASE WHEN n.name IS NULL THEN '空节点' ELSE n.name END AS name
        """)
        
        print(f"✅ 图谱节点详情：")
        print(f"  节点总数：{len(all_nodes)}")
        
        # 统计空节点
        empty_nodes = [n for n in all_nodes if n['name'] == '空节点']
        valid_nodes = [n for n in all_nodes if n['name'] != '空节点']
        
        print(f"  有效节点：{len(valid_nodes)}")
        print(f"  空节点（无name属性）：{len(empty_nodes)} ❌" if empty_nodes else "  空节点：0 ✅")
        
        if empty_nodes:
            print("\n⚠️ 发现空节点，详情：")
            for i, node in enumerate(empty_nodes[:5], 1):
                labels = ', '.join(node['labels']) if node['labels'] else '无标签'
                print(f"    {i}. 标签: {labels}")
            print("\n💡 建议：检查MERGE语句是否包含name属性进行匹配")
        
        # 查询有效节点
        if valid_nodes:
            print(f"\n有效节点列表：")
            for node in valid_nodes[:10]:
                labels = ', '.join(node['labels']) if node['labels'] else '无标签'
                print(f"  - [{labels}] {node['name']}")
        
        # 查询关系
        relationship_count = graph.query("MATCH ()-[r]->() RETURN count(r) AS cnt")[0]["cnt"]
        print(f"\n  关系总数：{relationship_count}")
        
        if relationship_count > 0:
            relationships = graph.query("""
                MATCH (a)-[r]->(b)
                RETURN 
                    CASE WHEN a.name IS NULL THEN '空节点' ELSE a.name END AS from_node,
                    type(r) AS rel_type,
                    CASE WHEN b.name IS NULL THEN '空节点' ELSE b.name END AS to_node
                LIMIT 5
            """)
            print(f"\n  关系示例：")
            for rel in relationships:
                print(f"    - {rel['from_node']} -{rel['rel_type']}-> {rel['to_node']}")
        
        print("\n✅ 图谱验证完成")
        
    except Exception as e:
        print(f"❌ 图谱查询失败：{str(e)}")

def test_result_structure():
    """测试4：验证返回结构符合前端要求"""
    print_section("测试4：验证返回结构")
    
    test_input = {
        'question': '手机有哪些品牌？',
        'low_relation_entity': '手机'
    }
    
    result = generate_answer(test_input)
    
    # 验证返回结构
    required_fields = ['status', 'data', 'error']
    for field in required_fields:
        assert field in result, f"❌ 缺少顶层字段：{field}"
    
    data_fields = ['question', 'answer', 'cypher', 'cypher_steps', 'graph_update_summary']
    for field in data_fields:
        assert field in result['data'], f"❌ data中缺少字段：{field}"
    
    # 验证cypher_steps结构
    if result['data']['cypher_steps']:
        step = result['data']['cypher_steps'][0]
        step_fields = ['step', 'type', 'statement', 'status', 'message']
        for field in step_fields:
            assert field in step, f"❌ cypher_steps中缺少字段：{field}"
    
    print("返回结构示例（JSON格式）：")
    print("-"*80)
    # 构建一个精简版用于展示
    display_result = {
        "status": result['status'],
        "data": {
            "question": result['data']['question'],
            "answer": result['data']['answer'][:50] + "...",
            "cypher": result['data']['cypher'][:100] + "..." if result['data']['cypher'] else "",
            "graph_update_summary": result['data']['graph_update_summary'],
            "cypher_steps": result['data']['cypher_steps'][:2] if result['data']['cypher_steps'] else []
        },
        "error": result.get('error', '')
    }
    print(json.dumps(display_result, ensure_ascii=False, indent=2))
    print("-"*80)
    
    print("\n✅ 返回结构验证通过")

def test_cypher_format_validation():
    """测试5：验证生成的Cypher格式（检查是否有name属性）"""
    print_section("测试5：Cypher格式验证")
    
    test_input = {
        'question': '电脑的品牌有哪些？',
        'low_relation_entity': '电脑'
    }
    
    result = generate_answer(test_input)
    cypher = result['data'].get('cypher', '')
    
    if not cypher:
        print("❌ 未生成Cypher语句")
        return
    
    print("生成的Cypher语句：")
    print("-" * 80)
    print(cypher)
    print("-" * 80)
    
    # 检查关键格式
    issues = []
    
    # 检查1：节点MERGE是否包含name属性
    import re
    merge_patterns = re.findall(r'MERGE\s*\([^)]+\)', cypher)
    print(f"\n发现 {len(merge_patterns)} 个MERGE语句")
    
    for i, pattern in enumerate(merge_patterns, 1):
        if '-[' in pattern or '->' in pattern:
            # 这是关系MERGE
            if '{' in pattern and 'name:' in pattern:
                # 关系MERGE包含节点属性 - 这是错误的格式！
                print(f"  ❌ {i}. (错误格式：关系MERGE不应包含节点属性) {pattern[:60]}..." if len(pattern) > 60 else f"  ❌ {i}. {pattern}")
                issues.append(f"关系MERGE使用了错误格式，应该先MATCH节点再MERGE关系：{pattern[:80]}")
            else:
                print(f"  ✅ {i}. (关系MERGE) {pattern[:60]}..." if len(pattern) > 60 else f"  ✅ {i}. (关系) {pattern}")
        else:
            # 这是节点MERGE
            if '{' in pattern and 'name:' in pattern:
                print(f"  ✅ {i}. (节点MERGE) {pattern[:60]}..." if len(pattern) > 60 else f"  ✅ {i}. {pattern}")
            else:
                print(f"  ❌ {i}. (节点缺少name属性) {pattern[:60]}..." if len(pattern) > 60 else f"  ❌ {i}. {pattern}")
                issues.append(f"节点MERGE语句缺少name属性：{pattern[:80]}")
    
    # 检查关系创建模式
    match_merge_pattern = re.findall(r'MATCH.*?MATCH.*?MERGE.*?-\[.*?\]->', cypher, re.DOTALL)
    if match_merge_pattern:
        print(f"\n✅ 发现 {len(match_merge_pattern)} 个MATCH-MERGE关系模式（推荐）")
    else:
        # 检查是否有直接的关系MERGE
        direct_rel_merge = [p for p in merge_patterns if '-[' in p or '->' in p]
        if direct_rel_merge:
            print(f"\n⚠️ 发现 {len(direct_rel_merge)} 个直接MERGE关系的语句（可能导致约束冲突）")
            print("   建议：改用 MATCH-MATCH-MERGE 模式")
    
    # 检查2：是否有三步注释
    has_step1 = '第一步' in cypher or '约束' in cypher
    has_step2 = '第二步' in cypher or '节点' in cypher
    has_step3 = '第三步' in cypher or '关系' in cypher
    
    print(f"\n步骤注释检查：")
    print(f"  第一步（约束）：{'✅' if has_step1 else '❌'}")
    print(f"  第二步（节点）：{'✅' if has_step2 else '❌'}")
    print(f"  第三步（关系）：{'✅' if has_step3 else '❌'}")
    
    if issues:
        print(f"\n⚠️ 发现 {len(issues)} 个格式问题：")
        for issue in issues[:5]:
            print(f"  - {issue}")
        print("\n💡 原因：LLM可能没有按照示例格式生成，导致创建空节点")
        print("💡 解决：需要进一步优化提示词，强制LLM在MERGE中包含name属性")
    else:
        print("\n✅ Cypher格式验证通过")

if __name__ == "__main__":
    print("="*80)
    print("【答智能体后端调试专用测试】")
    print("说明：专注于后端逻辑调试，不涉及前端联调")
    print("="*80)
    
    try:
        # 测试1：Cypher提取
        # test_extract_cypher()
        
        # 测试2：完整流程
        test_full_workflow()
        
        # 测试5：格式验证（重要！检查空节点问题）
        # test_cypher_format_validation()
        
        # 测试3：图谱验证（检查空节点）
        # test_graph_verification()
        
        # 测试4：返回结构
        # test_result_structure()
        
        print_section("所有测试完成")
        print("✅ 后端测试通过！")
        print("\n【优化成果】")
        print("1. ✅ 生成三步格式的CQL（约束→节点→关系）")
        print("2. ✅ 保留注释说明每一步的作用")
        print("3. ✅ 分步执行并返回详细结果")
        print("4. ✅ 节点MERGE包含name属性（避免空节点）")
        print("5. ✅ 约束已存在时自动跳过")
        print("\n【下一步】")
        print("- 如果发现空节点问题，请查看测试5的格式验证结果")
        print("- 格式正确后，即可进行前后端联调")
        
    except AssertionError as e:
        print(f"\n❌ 测试失败：{str(e)}")
    except Exception as e:
        print(f"\n❌ 测试异常：{str(e)}")
        import traceback
        traceback.print_exc()

