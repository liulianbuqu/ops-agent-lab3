"""
实验三：智能监控问答助手（场景一）

一个基于 LangChain + DeepSeek 构建的智能监控问答助手，
将 Prometheus 查询能力封装为智能体工具，使运维人员可以通过
自然语言向智能体提问，由智能体自主选择合适的 PromQL 查询语句、
调用 Prometheus API、汇总数据并生成可读的分析报告。

使用方式：
  1. 配置环境变量或 .env 文件：
       DEEPSEEK_API_KEY=sk-你的API Key
       DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
       DEEPSEEK_MODEL=deepseek-chat
  2. 运行：python main.py

作者: 智能体服务实验
"""
import os
import sys

from core.helper.logger import get_logger
from core.agent_builder import MonitorAgent


def main():
    """主入口函数。"""
    # 确保日志目录和图表目录存在
    log_dir = "./output/logs"
    chart_dir = "./output/charts"
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(chart_dir, exist_ok=True)

    # 初始化日志记录器
    logger = get_logger(save_dir=log_dir, task_name="monitor_agent")

    # ============================================================
    # 创建智能监控问答助手
    # ============================================================
    logger.info("正在初始化 MonitorAgent...")
    agent = MonitorAgent(logger=logger, verbose=True)

    # ============================================================
    # 示例一：多步骤健康检查（默认）
    # 用户通过自然语言描述，智能体自主规划步骤并调用工具
    # ============================================================
    user_input = """请帮我检查 bookinfo 命名空间的整体运行状况：
1. 首先检查 Prometheus 是否正常运行
2. 查询 bookinfo 下所有 Pod 的 CPU 使用情况
3. 查询 bookinfo 下所有 Pod 的内存使用情况
4. 查询各个 Pod 的重启次数
5. 汇总成一份完整的健康状态报告
    """

    # ============================================================
    # 示例二：趋势分析与可视化
    # 智能体自动查询时序数据并生成 matplotlib 折线图
    # ============================================================
    # user_input = "reviews-v2 最近五分钟的 CPU 使用趋势如何？帮我生成趋势图"

    # ============================================================
    # 示例三：快速问答（单次查询）
    # 智能体根据问题自动匹配最合适的监控工具
    # ============================================================
    # user_input = "现在 bookinfo 各个服务的内存占用情况怎么样？"
    # user_input = "bookinfo 命名空间整体健康状态如何？"
    # user_input = "查看 bookinfo 所有 Pod 的重启次数"
    # user_input = "查看 bookinfo 各服务的网络流量情况"
    # user_input = "productpage 的 CPU 占用是多少"

    # ============================================================
    # 启动智能体
    # ============================================================
    logger.info(f"用户任务: {user_input[:100]}...")
    response = agent.invoke(user_input)

    print(f"\n{'='*60}")
    print(f"最终结果:")
    print(f"{'='*60}")
    print(response['output'])
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
