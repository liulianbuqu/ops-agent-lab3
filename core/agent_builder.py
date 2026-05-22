"""
智能体构建模块
组装 LLM、Tools、Prompt 为完整的 ReAct Agent

本模块专为"智能监控问答助手（场景一）"设计，
聚焦于 Prometheus 指标查询与自然语言问答。
"""
from langchain.agents import initialize_agent, AgentType
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from core.helper.llm_util import init_llm
from core.prompts.ops_agent_prompt import MONITORING_SYSTEM_PROMPT

from core.tools.monitor_tools import (
    prometheus_query_tool,
    query_pod_cpu_usage,
    query_pod_memory_usage,
    query_pod_restart_count,
    query_namespace_health_report,
    query_cpu_trend,
    query_memory_trend,
    query_pod_network_io,
    prometheus_health_check,
    jaeger_query_tool,
)
from core.tools.failure_tools import (
    failure_diagnosis_tool,
)


class MonitorAgent:
    """
    MonitorAgent — 智能监控问答助手

    一个基于 LangChain ReAct 模式的智能监控助手，
    专为"智能监控问答助手（场景一）"设计。
    
    核心能力：
    - 通过自然语言查询 Prometheus 中的 CPU、内存、网络等指标
    - 自动选择合适的 PromQL 并调用 Prometheus API
    - 生成结构化的监控分析报告
    - 支持时序数据趋势分析与 matplotlib 可视化
    - 一站式命名空间健康评估
    - 故障自诊断（当查询失败时分析根因）
    """

    def __init__(self, logger=None, verbose: bool = True):
        """
        初始化 MonitorAgent。

        Args:
            logger: 可选的日志记录器实例
            verbose: 是否输出详细的 ReAct 执行日志
        """
        self.logger = logger
        self.verbose = verbose

        # 初始化 LLM
        self.llm = init_llm()

        # 注册所有工具（以监控工具为核心）
        self.tools = self._init_tools()

        # 构建智能体
        self.agent = self._build_agent()

        if self.logger:
            self.logger.info(
                f"MonitorAgent 初始化完成，已注册 {len(self.tools)} 个监控工具"
            )

    def _init_tools(self):
        """初始化并返回所有可用的监控工具列表。"""
        return [
            # ===== 监控专用工具（9个） =====
            prometheus_query_tool,          # 通用 PromQL 底层查询
            query_pod_cpu_usage,            # Pod CPU 使用率排名
            query_pod_memory_usage,         # Pod 内存使用排名
            query_pod_restart_count,        # Pod 重启次数检测
            query_namespace_health_report,  # 一站式命名空间健康报告
            query_cpu_trend,                # CPU 趋势 + 折线图
            query_memory_trend,             # 内存趋势 + 折线图
            query_pod_network_io,           # 网络 I/O 查询
            prometheus_health_check,        # Prometheus 健康检查

            # ===== 分布式追踪 =====
            jaeger_query_tool,              # Jaeger 调用链查询

            # ===== 故障诊断 =====
            failure_diagnosis_tool,         # 基于 LLM 的故障根因分析
        ]

    def _build_agent(self):
        """
        构建 ReAct Agent。
        使用 STRUCTURED_CHAT 模式 + 自定义监控系统提示词，
        使智能体能够精准理解监控场景下的自然语言查询并调用正确的工具。
        """
        # 构建自定义提示词模板
        prompt = ChatPromptTemplate.from_messages([
            ("system", MONITORING_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent_executor = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=self.verbose,
            max_iterations=30,
            max_execution_time=600,
            handle_parsing_errors=True,
            early_stopping_method="force",
            agent_kwargs={
                "system_message": MONITORING_SYSTEM_PROMPT,
                "extra_prompt_messages": [MessagesPlaceholder(variable_name="agent_scratchpad")],
            },
        )

        return agent_executor

    def invoke(self, query: str) -> dict:
        """
        执行智能体任务。

        接收用户的自然语言指令，启动 ReAct 循环，
        智能体将自主规划步骤、调用工具、观察结果，直至任务完成。

        Args:
            query: 用户的自然语言任务描述

        Returns:
            dict: 智能体的最终输出
        """
        if self.logger:
            self.logger.info(f"用户输入: {query}")

        print(f"\n{'='*60}")
        print(f"  MonitorAgent 开始执行监控任务...")
        print(f"{'='*60}\n")

        try:
            response = self.agent.invoke({"input": query})

            if self.logger:
                self.logger.info(f"智能体输出: {response.get('output', '')}")

            print(f"\n{'='*60}")
            print(f"  任务执行完成！")
            print(f"{'='*60}\n")

            return response

        except Exception as e:
            error_msg = f"智能体执行异常: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            print(f"\n❌ {error_msg}")
            return {"output": error_msg, "error": str(e)}
