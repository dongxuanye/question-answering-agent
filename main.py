from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware  # 导入 CORS 中间件
from pydantic import BaseModel
from typing import List
import time
import os
from config import WORKFLOW_CONFIG
from tools import get_graph_data, execute_neo4j_query
from ask_agent import generate_question
from answer_agent import generate_answer

app = FastAPI(title="知识图谱问答智能体")

# ===================== 关键：添加 CORS 跨域配置 =====================
# 允许的前端 Origin（替换为你的前端实际地址，开发环境可直接用 ["*"] 测试）
ALLOWED_ORIGINS = [
    "http://172.18.48.1:5173",  # 你的前端实际访问地址（必须包含）
    "http://localhost:5173",     # 本地开发备用地址
    "http://127.0.0.1:5173",    # 本地开发备用地址
    # "*",  # 开发环境快速测试可启用（生产环境必须替换为具体地址！）
]

app.add_middleware(
    CORSMiddleware,  # 不带括号！
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ===================== 全局状态管理 =====================
workflow_running = False
ask_count = 0
active_connections: List[WebSocket] = []

class SignalRequest(BaseModel):
    signal: str

# ===================== WebSocket通信 =====================
async def notify_clients(message: dict):
    for connection in active_connections:
        await connection.send_json(message)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    print(f"新客户端连接，当前连接数：{len(active_connections)}")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"status": "alive"})
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print(f"客户端断开连接，当前连接数：{len(active_connections)}")

# ===================== API路由 =====================
@app.get("/api/graph-data")
async def fetch_graph_data():
    try:
        data = get_graph_data()
        # 包裹前端要求的外层格式
        return {
            "code": 200,
            "message": "success",
            "data": data
        }
    except Exception as e:
        # 统一错误响应格式
        return {
            "code": 500,
            "message": f"图谱查询失败: {str(e)}",
            "data": None
        }

@app.post("/api/signal")
async def handle_signal(request: SignalRequest, background_tasks: BackgroundTasks):
    global workflow_running, ask_count
    if request.signal == "ask" and not workflow_running:
        workflow_running = True
        ask_count = 0
        background_tasks.add_task(run_workflow)
        return {"status": "success", "message": "工作流已启动"}
    elif request.signal == "stop":
        workflow_running = False
        return {"status": "success", "message": "工作流已停止"}
    else:
        return {"status": "error", "message": "无效信号或工作流已在运行"}

# ===================== 核心工作流 =====================
async def run_workflow():
    global workflow_running, ask_count
    print("工作流启动，开始问答循环...")
    try:
        ask_result={"status": "success"}
        while workflow_running and ask_count < WORKFLOW_CONFIG["max_ask_count"]:
            # 1. 调用问智能体
            print(f"\n--- 第{ask_count + 1}轮：调用问智能体 ---")
            ask_result = generate_question()

            # 关键判断：问智能体返回error（无实体）→ 终止工作流
            if ask_result["status"] == "error":
                error_msg = f"问智能体报错：{ask_result['error']}"
                await notify_clients({
                    "role": "system",
                    "status": "error",
                    "content": error_msg,
                    "timestamp": time.time()
                })
                print(error_msg)
                break  # 中断循环，停止工作流

            # 2. 问智能体正常（success/warning）→ 继续调用答智能体
            if ask_result["status"] == "warning":
                warn_msg = f"问智能体警告：{ask_result['error']}"
                await notify_clients({
                    "role": "ask",
                    "status": "warning",
                    "content": warn_msg,
                    "timestamp": time.time()
                })
                print(warn_msg)

            # 提取问智能体结果
            question = ask_result["data"].get("question", "")
            entity_label = ask_result["data"].get("entity_label", "")
            entity_name = ask_result["data"].get("entity_name", "")
            
            if not question:
                error_msg = "问智能体未生成有效问题，终止本轮流程"
                await notify_clients({
                    "role": "system",
                    "status": "error",
                    "content": error_msg,
                    "timestamp": time.time()
                })
                print(error_msg)
                ask_count += 1
                continue

            # 推送问智能体结果给前端
            await notify_clients({
                "role": "ask",
                "status": "success",
                "content": {
                    "question": question,
                    "core_entity": f"{entity_label}:{entity_name}" if entity_label else entity_name
                },
                "timestamp": time.time()
            })
            print(f"问智能体生成：问题={question}")
            print(f"  核心实体Label={entity_label}，实体名={entity_name}")

            # 3. 调用答智能体
            print(f"--- 第{ask_count + 1}轮：调用答智能体 ---")
            answer_input = {
                "question": question,
                "entity_label": entity_label,
                "entity_name": entity_name
            }
            answer_result = generate_answer(answer_input)
            print("答智能体输出结果：",answer_result)
            
            # 推送答智能体结果给前端（包含分步执行结果）
            await notify_clients({
                "role": "answer",
                "status": answer_result["status"],
                "content": {
                    "question": answer_result["data"].get("question", ""),
                    "answer": answer_result["data"].get("answer", ""),
                    "cypher": answer_result["data"].get("cypher", ""),
                    "graph_update_summary": answer_result["data"].get("graph_update_summary", ""),
                    "cypher_steps": answer_result["data"].get("cypher_steps", [])
                },
                "error": answer_result.get("error", ""),
                "timestamp": time.time()
            })
            
            # 打印执行摘要
            print(f"答智能体结果：状态={answer_result['status']}")
            print(f"  答案：{answer_result['data'].get('answer', '')[:50]}...")
            print(f"  图谱更新：{answer_result['data'].get('graph_update_summary', '无')}")
            if answer_result["data"].get("cypher_steps"):
                print(f"  执行步骤：共 {len(answer_result['data']['cypher_steps'])} 条")

            # 5. 计数+延迟
            ask_count += 1
            time.sleep(WORKFLOW_CONFIG["loop_delay"])

        # 工作流结束通知
        end_msg = f"工作流已结束（触发{ask_count}次ask信号，{'因无有效实体提前终止' if 'ask_result' in locals() and ask_result.get('status') == 'error' else '达到最大次数正常终止'}）"
        await notify_clients({
            "role": "system",  # 补充 role 字段，前端统一处理
            "status": "finished",
            "content": end_msg,
            "timestamp": time.time()
        })
        print(end_msg)
    except Exception as e:
        workflow_running = False
        error_msg = f"工作流异常结束：{str(e)}"
        await notify_clients({
            "role": "system",  # 补充 role 字段
            "status": "error",
            "content": error_msg,
            "timestamp": time.time()
        })
        print(error_msg)
    finally:
        workflow_running = False  # 确保最终重置工作流状态

if __name__ == "__main__":
    import uvicorn
    if not os.path.exists("prompts"):
        os.makedirs("prompts")
        print("已自动创建prompts文件夹，请放入提示词文件")
        # http://127.0.0.1:8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)