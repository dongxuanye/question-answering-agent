"""
消耗统计测试脚本
模拟运行工作流并输出消耗统计表格
"""

import sys
import time
from cost_tracker import get_tracker


def simulate_workflow():
    """模拟一个完整的工作流运行"""
    
    tracker = get_tracker()
    tracker.reset()
    tracker.start_workflow()
    
    print("=" * 80)
    print("开始模拟工作流...")
    print("=" * 80)
    
    # 模拟3轮问答
    for round_num in range(1, 4):
        print(f"\n--- 第{round_num}轮问答 ---")
        
        # 1. 问智能体调用Cypher查询
        print(f"  [问智能体] 查询Neo4j获取实体...")
        tracker.record_ask_cypher_query()
        time.sleep(0.1)
        
        # 2. 问智能体调用LLM生成问题
        print(f"  [问智能体] 调用LLM生成问题...")
        # 模拟token消耗（提示词约100 token，输出约50 token）
        input_tokens = 120 + round_num * 10  # 随着轮次增加，上下文稍微增加
        output_tokens = 45 + round_num * 5
        tracker.record_ask_llm_call(input_tokens, output_tokens)
        time.sleep(0.2)
        print(f"      Token消耗: 输入={input_tokens}, 输出={output_tokens}")
        
        # 3. 答智能体调用搜索工具
        print(f"  [答智能体] 调用搜索API...")
        tracker.record_answer_search_call()
        time.sleep(0.15)
        
        # 4. 答智能体调用LLM汇总并生成Cypher
        print(f"  [答智能体] 调用LLM生成答案和Cypher...")
        # 模拟token消耗（提示词+搜索结果约300 token，输出约200 token）
        input_tokens = 350 + round_num * 20
        output_tokens = 180 + round_num * 15
        tracker.record_answer_llm_call(input_tokens, output_tokens)
        time.sleep(0.25)
        print(f"      Token消耗: 输入={input_tokens}, 输出={output_tokens}")
        
        # 5. 执行Cypher语句（模拟生成了3-5条语句）
        statement_count = 3 + (round_num % 3)
        print(f"  [答智能体] 执行Cypher更新图谱（{statement_count}条语句）...")
        tracker.record_cypher_execution(statement_count)
        time.sleep(0.1)
        
        print(f"  第{round_num}轮完成")
    
    tracker.end_workflow()
    
    print("\n" + "=" * 80)
    print("工作流模拟完成！")
    print("=" * 80)
    
    return tracker


def main():
    """主函数"""
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "问答智能体消耗统计测试脚本" + " " * 24 + "║")
    print("╚" + "═" * 78 + "╝\n")
    
    # 运行模拟
    tracker = simulate_workflow()
    
    # 打印统计表格
    tracker.print_table()
    
    # 额外打印详细信息
    print("\n" + "=" * 130)
    print("详细活动统计:")
    print("=" * 130)
    
    summary = tracker.get_summary()
    
    for key, activity in summary["activities"].items():
        if activity["count"] > 0:
            print(f"\n活动: {activity['description']}")
            print(f"  - 调用次数: {activity['count']}")
            if activity["total_tokens"] > 0:
                print(f"  - Token消耗: {activity['total_tokens']} (输入:{activity['input_tokens']}, 输出:{activity['output_tokens']})")
            if activity["api_calls"] > 0:
                print(f"  - API调用: {activity['api_calls']}次")
    
    print("\n" + "=" * 130)
    
    # 成本估算（基于Deepseek价格）
    print("\n" + "=" * 130)
    print("成本估算（基于Deepseek V3定价）:")
    print("=" * 130)
    
    total_input = sum(act["input_tokens"] for act in summary["activities"].values())
    total_output = sum(act["output_tokens"] for act in summary["activities"].values())
    total_tokens = total_input + total_output
    
    # Deepseek V3价格（示例）：
    # 输入: 0.5元/百万token
    # 输出: 2.0元/百万token
    input_cost = total_input * 0.5 / 1_000_000
    output_cost = total_output * 2.0 / 1_000_000
    total_cost = input_cost + output_cost
    
    print(f"总输入Token: {total_input:,}")
    print(f"总输出Token: {total_output:,}")
    print(f"总Token消耗: {total_tokens:,}")
    print(f"\n估算成本:")
    print(f"  - 输入Token成本: {input_cost:.6f}元 ({total_input} tokens × 0.5元/百万)")
    print(f"  - 输出Token成本: {output_cost:.6f}元 ({total_output} tokens × 2.0元/百万)")
    print(f"  - 总成本: {total_cost:.6f}元")
    print(f"\n注: 以上为模拟数据，实际消耗以运行时记录为准")
    print("=" * 130)
    
    # 输出使用说明
    print("\n" + "=" * 130)
    print("使用说明:")
    print("=" * 130)
    print("1. 在实际运行中，main.py会自动追踪并在工作流结束时打印统计表格")
    print("2. 所有LLM调用都会自动记录token消耗（如果API返回了usage信息）")
    print("3. 搜索工具、数据库操作都会自动计数")
    print("4. 表格会在控制台输出，方便查看各项活动的消耗情况")
    print("=" * 130 + "\n")


if __name__ == "__main__":
    main()

