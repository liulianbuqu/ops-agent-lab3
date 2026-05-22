"""
智能体构建模块
组装 LLM、Tools、Prompt 为完整的 ReAct Agent
"""
from langchain.agents import initialize_agent, AgentType
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from core.helper.llm_util import init_llm
from core.prompts.ops_agent_prompt import MONITORING_SYSTEM_PROMPT

from core.tools.file_tools import (
    file_read_tool,
    file_write_tool,
    file_list_tool,
)
from core.tools.docker_tools import (
    dockerfile_generate_tool,
    image_build_tool,
    container_run_tool,
    container_exec_cmd_tool,
    container_logs_tool,
)
from core.tools.k8s_tools import (
    k8s_yaml_generate_tool,
    k8s_apply_tool,
    k8s_pod_status_tool,
    k8s_delete_tool,
    k8s_namespace_tool,
)
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


class OpsAgent:
    """
    Ops Agent — 运维智能体

    一个基于 LangChain ReAct 模式的智能运维助手，
    能够通过自然语言交互完成 Docker/K8s 部署、监控查询、故障诊断等任务。
    """

    def __init__(self, logger=None, verbose: bool = True):
        """
        初始化 OpsAgent。

        Args:
            logger: 可选的日志记录器实例
            verbose: 是否输出详细的 ReAct 执行日志
        """
        self.logger = logger
        self.verbose = verbose

        # 初始化 LLM
        self.llm = init_llm()

        # 注册所有工具
        self.tools = self._init_tools()

        # 构建智能体
        self.agent = self._build_agent()

        if self.logger:
            self.logger.info(
                f"OpsAgent 初始化完成，已注册 {len(self.tools)} 个工具"
            )

    def _init_tools(self):
        """初始化并返回所有可用的工具列表（使用 @tool 装饰器原生的结构化工具）。"""
        return [
            # ===== 文件操作工具 =====
            file_read_tool,
            file_write_tool,
            file_list_tool,

            # ===== Docker 工具 =====
            dockerfile_generate_tool,
            image_build_tool,
            container_run_tool,
            container_exec_cmd_tool,
            container_logs_tool,

            # ===== Kubernetes 工具 =====
            k8s_yaml_generate_tool,
            k8s_apply_tool,
            k8s_pod_status_tool,
            k8s_delete_tool,
            k8s_namespace_tool,

            # ===== 监控工具 =====
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

            # ===== 故障诊断工具 =====
            failure_diagnosis_tool,
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
        print(f"  OpsAgent 开始执行任务...")
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
