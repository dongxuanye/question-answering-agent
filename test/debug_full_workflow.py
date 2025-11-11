import time
from config import WORKFLOW_CONFIG
from tools import get_graph_data, execute_neo4j_query
from ask_agent import generate_question
from answer_agent import generate_answer


def debug_full_workflow():
    """全流程调试函数，模拟main.py中的工作流逻辑"""
    print("=== 全流程调试开始 ===")
    print(f"配置参数: 最大提问次数={WORKFLOW_CONFIG['max_ask_count']}, 循环延迟={WORKFLOW_CONFIG['loop_delay']}秒")

    workflow_running = True
    ask_count = 0
    ask_result = None  # 用于记录最后一次问智能体结果

    try:
        while workflow_running and ask_count < WORKFLOW_CONFIG["max_ask_count"]:
            # 1. 模拟调用问智能体
            print(f"\n--- 第{ask_count + 1}轮：调用问智能体 ---")
            ask_result = generate_question()
            print(f"问智能体返回: {ask_result}")

            # 检查问智能体错误状态
            if ask_result["status"] == "error":
                error_msg = f"问智能体报错：{ask_result['error']}"
                print(f"系统通知: {error_msg}")
                break  # 终止工作流

            # 处理警告状态
            if ask_result["status"] == "warning":
                warn_msg = f"问智能体警告：{ask_result['error']}"
                print(f"系统通知: {warn_msg}")

            # 提取问题和核心实体
            question = ask_result["data"].get("question", "")
            core_entity = ask_result["data"].get("low_relation_entity", "")

            if not question:
                error_msg = "问智能体未生成有效问题，终止本轮流程"
                print(f"系统通知: {error_msg}")
                ask_count += 1
                continue

            print(f"问智能体输出: 问题='{question}', 核心实体='{core_entity}'")

            # 2. 模拟调用答智能体
            print(f"--- 第{ask_count + 1}轮：调用答智能体 ---")
            answer_input = {
                "question": question,
                "low_relation_entity": core_entity
            }
            answer_result = generate_answer(answer_input)
            print(f"答智能体返回: {answer_result}")

            # 3. 模拟执行Cypher（若有）
            if answer_result["status"] == "success" and answer_result["data"].get("cypher"):
                cypher = answer_result["data"]["cypher"]
                print(f"执行Cypher: {cypher}")
                execute_result = execute_neo4j_query(cypher)
                print(f"Cypher执行结果: {execute_result}")

            # 4. 计数+延迟
            ask_count += 1
            if ask_count < WORKFLOW_CONFIG["max_ask_count"]:
                print(f"等待{WORKFLOW_CONFIG['loop_delay']}秒后进入下一轮...")
                time.sleep(WORKFLOW_CONFIG["loop_delay"])

        # 工作流结束信息
        end_msg = (f"工作流已结束（触发{ask_count}次ask信号，"
                   f"{'因无有效实体提前终止' if ask_result and ask_result.get('status') == 'error' else '达到最大次数正常终止'}）")
        print(f"\n{end_msg}")

    except Exception as e:
        workflow_running = False
        error_msg = f"工作流异常结束：{str(e)}"
        print(f"\n错误通知: {error_msg}")
    finally:
        print("\n=== 全流程调试结束 ===")


if __name__ == "__main__":
    # 可选：调试时先获取图谱数据
    print("获取初始图谱数据...")
    graph_data = get_graph_data()
    print(f"图谱数据预览: {str(graph_data)[:200]}...")  # 只显示部分数据

    # 启动全流程调试
    debug_full_workflow()