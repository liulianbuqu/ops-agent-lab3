"""
实验三：Ops Agent — 运维智能体

一个基于 LangChain + DeepSeek 构建的智能运维助手，
支持 Docker 容器化、Kubernetes 集群部署、监控查询与故障诊断。

参考场景（任选其一）：
  场景一：智能监控问答助手 — 自然语言查询 Prometheus 指标
  场景二：故障注入与智能诊断闭环 — 多工具协同定位根因
  场景三：K8s 自动化部署流水线 — 从源码到 K8s 集群的全自动部署  [推荐]
  场景四：接入现有智能体平台 — Dify/Coze 等平台的工具集成

使用方式：
  1. 配置环境变量或 .env 文件：
       DEEPSEEK_API_KEY=sk-你的API Key
       DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
       DEEPSEEK_MODEL=deepseek-chat
  2. 运行：uv run main.py  或  python main.py

作者: 智能体服务实验
"""
import os
import random
import numpy as np

from core.helper.logger import get_logger
from core.agent_builder import OpsAgent


def random_seed(seed: int = 42):
    """设置随机种子，确保结果可复现。"""
    random.seed(seed)
    np.random.seed(seed)


def main():
    """主入口函数。"""
    random_seed(42)

    # 确保日志目录和图表目录存在
    log_dir = "./output/logs"
    chart_dir = "./output/charts"
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(chart_dir, exist_ok=True)

    # 初始化日志记录器
    logger = get_logger(save_dir=log_dir, task_name="ops_agent")

    # ============================================================
    # 创建 Ops Agent
    # ============================================================
    logger.info("正在初始化 OpsAgent...")
    ops_agent = OpsAgent(logger=logger, verbose=True)

    # ============================================================
    # 场景一：智能监控问答助手（默认场景）
    # 用户通过自然语言查询 Prometheus 指标，智能体自主选择 PromQL
    # ============================================================
    user_input = """请帮我检查 bookinfo 命名空间的整体运行状况：
1. 首先检查 Prometheus 是否正常运行
2. 查询 bookinfo 下所有 Pod 的 CPU 使用情况
3. 查询 bookinfo 下所有 Pod 的内存使用情况
4. 查询各个 Pod 的重启次数
5. 汇总成一份完整的健康状态报告
    """

    # ============================================================
    # 场景一示例二：趋势分析与可视化
    # ============================================================
    # user_input = """
    # 我想查看 bookinfo 命名空间的详细情况：
    # 1. 查询各个 Pod 的 CPU 使用率和内存占用排名
    # 2. 查看 reviews-v2 最近 30 分钟的 CPU 使用趋势，帮我生成趋势图
    # 3. 查看 productpage 服务的内存变化趋势
    # 4. 检查各 Pod 的网络 I/O 情况
    # 5. 给我一份综合评估报告
    # """

    # ============================================================
    # 场景一示例三：快速问答
    # ============================================================
    # user_input = "现在 bookinfo 各个服务的内存占用情况怎么样？"
    # user_input = "reviews-v2 最近五分钟的 CPU 使用趋势如何？"
    # user_input = "bookinfo 命名空间整体健康状态如何？"
    # user_input = "查看 bookinfo 所有 Pod 的重启次数"

    # ============================================================
    # 启动智能体
    # ============================================================
    logger.info(f"用户任务: {user_input[:100]}...")
    response = ops_agent.invoke(user_input)

    print(f"\n最终结果:\n{response['output']}")


if __name__ == "__main__":
    main()
