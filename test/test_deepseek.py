# test_deepseek.py
from langchain_openai import ChatOpenAI
from config import DEEPSEEK_CONFIG

def test_deepseek():
    try:
        llm = ChatOpenAI(
            model_name=DEEPSEEK_CONFIG["model_name"],
            api_key=DEEPSEEK_CONFIG["api_key"],
            base_url=DEEPSEEK_CONFIG["url"],
            temperature=0.1
        )
        # 发送简单请求
        response = llm.invoke("你好，输出一个简单句子")
        print(f"LLM 响应成功：{response.content}")
        return True
    except Exception as e:
        print(f"LLM 调用失败：{str(e)}")
        return False

if __name__ == "__main__":
    test_deepseek()