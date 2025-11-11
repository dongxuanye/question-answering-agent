from ask_agent import generate_question, get_least_relationship_entity


def debug_ask_agent_full_flow():
    print("=" * 70)
    print("【完整流程】问智能体（模拟 ask 信号 → 调用工具 → 生成问题）")
    print("=" * 70)

    # 1. 模拟前端发送 ask 信号
    print("\n1. 模拟前端发送 ask 信号，触发问智能体...")
    result = generate_question()  # 现在返回字典格式

    # 2. 解析结果（模拟前端处理逻辑）
    if result["status"] == "success":
        print(f"✅ 执行成功！生成的问题：{result['data']}")

        # 验证工具调用有效性
        print("\n2. 验证工具调用有效性...")
        real_entity = get_least_relationship_entity()
        print(f"工具直接调用结果：{real_entity}")
        if real_entity in result["data"]:
            print("✅ 智能体已基于工具实体生成问题！")
        else:
            print(f"⚠️  警告：生成的问题未包含工具实体（实体：{real_entity}，问题：{result['data']}）")
    elif result["status"] == "warning":
        print(f"⚠️  业务警告：{result['data']}，错误详情：{result['error']}")
    else:  # error
        print(f"❌ 执行失败：{result['error']}")

    print("\n" + "=" * 70)
    print("【完整流程】问智能体调试结束")
    print("=" * 70)


if __name__ == "__main__":
    debug_ask_agent_full_flow()