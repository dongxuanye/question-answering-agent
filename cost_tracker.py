"""
消耗统计追踪器
用于记录问答智能体各项活动的token消耗、API调用次数等
"""

from dataclasses import dataclass, field
from typing import Dict, List
import time


@dataclass
class ActivityStats:
    """单个活动的统计信息"""
    name: str
    description: str
    count: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    api_calls: int = 0
    
    def add_llm_call(self, input_tokens: int = 0, output_tokens: int = 0):
        """记录一次LLM调用"""
        self.count += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += (input_tokens + output_tokens)
    
    def add_api_call(self):
        """记录一次API调用（如搜索）"""
        self.count += 1
        self.api_calls += 1
    
    def add_db_call(self):
        """记录一次数据库调用"""
        self.count += 1
    
    def increment(self):
        """简单计数加1"""
        self.count += 1


class CostTracker:
    """全局消耗追踪器"""
    
    def __init__(self):
        self.activities: Dict[str, ActivityStats] = {}
        self.start_time = None
        self.end_time = None
        self.workflow_started = False
        
        # 初始化所有活动类型
        self._init_activities()
    
    def _init_activities(self):
        """初始化所有活动类型"""
        activity_definitions = [
            ("workflow_start", "启动/触发图谱问答补全"),
            ("ask_cypher_query", "问智能体调用Cypher查询工具"),
            ("ask_llm_call", "问智能体调用LLM模型生成问题"),
            ("answer_search_call", "答智能体调用搜索工具"),
            ("answer_llm_call", "答智能体调用LLM汇总搜索结果并生成Cypher语句"),
            ("human_feedback", "人机评价机制（未开发）"),
            ("cypher_execution", "答智能体执行Cypher工具补充知识图谱"),
        ]
        
        for key, desc in activity_definitions:
            self.activities[key] = ActivityStats(name=key, description=desc)
    
    def start_workflow(self):
        """标记工作流开始"""
        if not self.workflow_started:
            self.start_time = time.time()
            self.workflow_started = True
            self.activities["workflow_start"].increment()
    
    def end_workflow(self):
        """标记工作流结束"""
        if self.workflow_started:
            self.end_time = time.time()
    
    def record_ask_cypher_query(self):
        """记录问智能体Cypher查询"""
        self.activities["ask_cypher_query"].add_db_call()
    
    def record_ask_llm_call(self, input_tokens: int = 0, output_tokens: int = 0):
        """记录问智能体LLM调用"""
        self.activities["ask_llm_call"].add_llm_call(input_tokens, output_tokens)
    
    def record_answer_search_call(self):
        """记录答智能体搜索调用"""
        self.activities["answer_search_call"].add_api_call()
    
    def record_answer_llm_call(self, input_tokens: int = 0, output_tokens: int = 0):
        """记录答智能体LLM调用"""
        self.activities["answer_llm_call"].add_llm_call(input_tokens, output_tokens)
    
    def record_cypher_execution(self, statement_count: int = 1):
        """记录Cypher执行（可指定执行了多少条语句）"""
        for _ in range(statement_count):
            self.activities["cypher_execution"].add_db_call()
    
    def get_duration(self) -> float:
        """获取工作流执行时长（秒）"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return time.time() - self.start_time
        return 0.0
    
    def reset(self):
        """重置所有统计"""
        self.__init__()
    
    def get_summary(self) -> Dict:
        """获取统计摘要"""
        return {
            "duration": self.get_duration(),
            "activities": {
                key: {
                    "description": stats.description,
                    "count": stats.count,
                    "total_tokens": stats.total_tokens,
                    "input_tokens": stats.input_tokens,
                    "output_tokens": stats.output_tokens,
                    "api_calls": stats.api_calls,
                }
                for key, stats in self.activities.items()
            }
        }
    
    def print_table(self):
        """打印漂亮的表格"""
        duration = self.get_duration()
        
        print("\n" + "="*130)
        print(f"问答智能体各活动消耗统计表（运行时长: {duration:.2f}秒）")
        print("="*130)
        
        # 表头
        header = f"| {'序号':^6} | {'活动':<40} | {'消耗描述':<50} | {'频次':^10} | {'Token消耗':^20} |"
        print(header)
        print("="*130)
        
        # 数据行
        rows = [
            (
                1,
                "启动/触发图谱问答补全",
                "无额外资源消耗（仅系统初始化开销）",
                f"{self.activities['workflow_start'].count}次（工作流启动时触发）",
                "0"
            ),
            (
                2,
                "问智能体调用Cypher查询工具",
                "Neo4j数据库查询资源，无模型token消耗",
                f"{self.activities['ask_cypher_query'].count}次",
                "0"
            ),
            (
                3,
                "问智能体调用LLM模型生成问题",
                "消耗Deepseek模型token（输入提示词+输出结果）",
                f"{self.activities['ask_llm_call'].count}次",
                f"输入:{self.activities['ask_llm_call'].input_tokens} / 输出:{self.activities['ask_llm_call'].output_tokens} / 总计:{self.activities['ask_llm_call'].total_tokens}"
            ),
            (
                4,
                "答智能体调用搜索工具",
                "消耗SerpAPI搜索次数，无模型token消耗",
                f"{self.activities['answer_search_call'].count}次",
                f"{self.activities['answer_search_call'].api_calls}次API调用"
            ),
            (
                5,
                "答智能体调用LLM汇总搜索结果并生成Cypher",
                "消耗Deepseek模型token（输入提示词+搜索结果+输出）",
                f"{self.activities['answer_llm_call'].count}次",
                f"输入:{self.activities['answer_llm_call'].input_tokens} / 输出:{self.activities['answer_llm_call'].output_tokens} / 总计:{self.activities['answer_llm_call'].total_tokens}"
            ),
            (
                6,
                "人机评价机制（未开发）",
                "待定",
                "待定",
                "0"
            ),
            (
                7,
                "答智能体执行Cypher工具补充知识图谱",
                "Neo4j数据库写入资源，无模型token消耗",
                f"{self.activities['cypher_execution'].count}次",
                "0"
            ),
        ]
        
        for row in rows:
            seq, activity, desc, freq, cost = row
            print(f"| {seq:^6} | {activity:<40} | {desc:<50} | {freq:^10} | {cost:<20} |")
            print("-"*130)
        
        print("="*130)
        
        # 汇总信息
        total_tokens = sum(stats.total_tokens for stats in self.activities.values())
        total_api_calls = sum(stats.api_calls for stats in self.activities.values())
        
        print(f"\n汇总统计:")
        print(f"  - 总Token消耗: {total_tokens}")
        print(f"  - LLM调用总次数: {self.activities['ask_llm_call'].count + self.activities['answer_llm_call'].count}")
        print(f"  - 外部API调用总次数: {total_api_calls}")
        print(f"  - 数据库查询次数: {self.activities['ask_cypher_query'].count}")
        print(f"  - 数据库写入次数: {self.activities['cypher_execution'].count}")
        print(f"  - 工作流运行时长: {duration:.2f}秒")
        print()


# 全局单例
_global_tracker = CostTracker()


def get_tracker() -> CostTracker:
    """获取全局追踪器实例"""
    return _global_tracker

