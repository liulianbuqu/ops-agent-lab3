# MonitorAgent — 智能监控问答助手

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-0.3.30-green)](https://langchain.com)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek%20Chat-orange)](https://deepseek.com)

基于 **LangChain + DeepSeek** 构建的智能监控问答助手。将 Prometheus 查询能力封装为具有清晰语义的智能体工具，使运维人员可以通过**自然语言**向智能体提问，由智能体自主选择合适的 PromQL 查询语句、调用 Prometheus API、汇总数据并生成可读的分析报告。

---

## 目录

- [场景描述](#场景描述)
- [核心能力](#核心能力)
- [技术架构](#技术架构)
- [环境准备](#环境准备)
- [快速开始](#快速开始)
- [演示示例](#演示示例)
- [工具参考手册](#工具参考手册)
- [项目结构](#项目结构)
- [常见问题](#常见问题)

---

## 场景描述

在传统的运维工作中，查询 Prometheus 监控指标需要运维人员具备 PromQL 语法知识，使用门槛较高。本场景将 Prometheus 查询能力封装为**具有清晰语义的智能体工具集**，实现以下目标：

1. **自然语言 → 监控指标**：用户用日常语言提问，智能体自动理解意图
2. **自动 PromQL 生成**：智能体根据问题类型选择最合适的 PromQL 查询
3. **智能数据分析**：不仅返回原始数据，还自动排序、格式化、异常检测、趋势判断
4. **可视化呈现**：趋势查询自动生成 matplotlib 折线图
5. **一站式报告**：聚合多项指标生成命名空间健康综合评估

**典型交互：**

```
用户：现在 bookinfo 各个服务的内存占用情况怎么样？

智能体：（自动调用 Prometheus 查询）
  💾 内存使用报告 — 命名空间: bookinfo
  ==================================================
    📦 productpage-v1-xxxxx    内存: 303.2 MiB
    📦 reviews-v1-xxxxx        内存: 152.8 MiB
    📦 reviews-v2-xxxxx        内存: 148.6 MiB
    📦 details-v1-xxxxx        内存: 54.3 MiB
    📦 ratings-v1-xxxxx        内存: 47.1 MiB
  ==================================================
    📈 总计内存使用: 839.9 MiB
    💡 分析: productpage 内存占用最高，占整体的 36.1%
    ✅ 所有 Pod 内存使用在正常范围内，无异常。
```

---

## 核心能力

### 智能体推理

| 能力 | 说明 |
|------|------|
| ReAct 推理循环 | Thought → Action → Observation 自主决策 |
| 11 个预注册监控工具 | 覆盖 CPU、内存、网络、重启、趋势、健康检查 |
| 结构化报告输出 | 工具返回格式化分析报告，智能体综合生成结论 |
| 故障自诊断 | 查询失败时自动调用 `failure_diagnosis_tool` 分析根因 |
| 多工具协同 | 自动组合多个工具完成复杂多步骤监控任务 |

### 监控指标覆盖

| 指标类型 | 工具名 | 说明 |
|---------|--------|------|
| 🖥️ CPU 使用率 | `query_pod_cpu_usage` | 按使用量降序排名，检测异常偏高 |
| 💾 内存使用量 | `query_pod_memory_usage` | 自动转换 MiB 格式，超 1 GiB 预警 |
| 🔄 Pod 重启次数 | `query_pod_restart_count` | 分级告警（🟢正常/🟡关注/🔴异常） |
| 🌐 网络 I/O | `query_pod_network_io` | 接收/发送速率表格展示 |
| 📈 CPU 趋势 | `query_cpu_trend` | 时序趋势分析 + matplotlib 折线图 |
| 📉 内存趋势 | `query_memory_trend` | 时序趋势分析 + 内存泄漏预警 |
| 📋 健康总览 | `query_namespace_health_report` | 一站式聚合 CPU+内存+重启 |
| ✅ Prometheus 健康 | `prometheus_health_check` | 检查 Prometheus 运行状态 |
| 🔗 调用链追踪 | `jaeger_query_tool` | Jaeger 分布式追踪查询 |

### 趋势可视化

趋势查询工具（`query_cpu_trend` / `query_memory_trend`）支持自动生成 matplotlib 折线图：

- 横轴：时间轴（格式 HH:MM）
- 纵轴：CPU 使用率（cores）或内存使用量（MiB）
- 每条线代表一个 Pod，使用 Tab10 色彩映射区分
- 标注图例、网格线
- 图表保存至 `output/charts/` 目录

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                    用户自然语言输入                           │
│  "bookinfo 各服务的内存占用情况怎么样？"                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  MonitorAgent (core/agent_builder.py)                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ReAct 循环: Thought → Action → Observation            │ │
│  │  LLM: DeepSeek Chat (temperature=0, max_retries=2)     │ │
│  │  系统提示词: MONITORING_SYSTEM_PROMPT                   │ │
│  │   - 角色定位: 监控专家                                   │ │
│  │   - 问题-工具映射表                                      │ │
│  │   - 输出风格规范: 结构化+Emoji                           │ │
│  └────────────────────────────────────────────────────────┘ │
└────────┬──────────┬──────────┬──────────┬───────────────────┘
         │          │          │          │
┌────────▼──┐ ┌─────▼─────┐ ┌─▼────────┐ ┌▼────────────────┐
│ 指标查询   │ │ 趋势分析   │ │ 健康总览  │ │ 故障诊断         │
│ ───────── │ │ ────────  │ │ ──────── │ │ ──────────────  │
│ CPU 使用率 │ │ 时序数据   │ │ 多指标    │ │ LLM 根因分析     │
│ 内存使用量 │ │ 折线图     │ │ 聚合评估   │ │ 修复建议         │
│ 重启次数   │ │ 趋势判断   │ │ 异常检测   │ │                 │
│ 网络 I/O   │ │ 图表保存   │ │ 报告生成   │ │                 │
└───────────┘ └───────────┘ └──────────┘ └─────────────────┘
         │          │          │          │
         └──────────┴──────────┴──────────┘
                      │
         ┌────────────▼────────────┐
         │   Prometheus API        │
         │   http://localhost:9090 │
         └─────────────────────────┘
```

### 技术栈

| 组件 | 技术选型 | 用途 |
|------|---------|------|
| **LLM** | DeepSeek Chat (OpenAI 兼容 API) | 智能体推理与决策 |
| **Agent 框架** | LangChain 0.3.30 (AgentExecutor) | ReAct 循环、工具绑定 |
| **监控数据源** | Prometheus 2.45+ | 指标存储与查询 |
| **Prometheus 客户端** | prometheus-api-client 0.5+ | PromQL 查询封装 |
| **可视化** | matplotlib 3.8+ | 趋势折线图 |
| **分布式追踪** | Jaeger | 调用链查询 |

---

## 环境准备

### 前置依赖

| 依赖 | 版本要求 | 用途 |
|------|---------|------|
| Python | ≥ 3.11 | 运行环境 |
| Prometheus | ≥ 2.45 | 监控数据源（需预先部署） |

### 安装 Python 依赖

```bash
# 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\Activate.ps1    # Windows
source .venv/bin/activate      # Linux/Mac

# 安装所有依赖
pip install -r requirements.txt
```

核心依赖说明：

| 包名 | 版本 | 用途 |
|------|------|------|
| `langchain` | 0.3.30 | Agent 框架核心 |
| `langchain-openai` | 0.2.14 | OpenAI 兼容 API 适配 |
| `prometheus-api-client` | ≥0.5.0 | Prometheus HTTP API 封装 |
| `matplotlib` | ≥3.8.0 | 趋势图可视化 |
| `python-dotenv` | ≥1.0.0 | 环境变量管理 |

---

## 配置 LLM

在项目根目录创建 `.env` 文件：

```ini
# DeepSeek API 配置
DEEPSEEK_API_KEY=sk-你的API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

> 本项目兼容所有 OpenAI API 格式的模型服务，只需修改 `base_url` 和 `model` 即可。

---

## 快速开始

确保 Prometheus 服务运行在 `http://localhost:9090`，且已配置采集 Kubernetes 集群的 cadvisor 和 kube-state-metrics 指标。

```bash
python main.py
```

默认执行**多步骤健康检查**——检查 Prometheus → 查询 CPU → 查询内存 → 查询重启 → 生成报告。

### 切换查询类型

编辑 `main.py`，选择不同的 `user_input`：

```python
# 趋势分析
user_input = "reviews-v2 最近五分钟的 CPU 使用趋势如何？帮我生成趋势图"

# 快速问答
user_input = "现在 bookinfo 各个服务的内存占用情况怎么样？"
user_input = "bookinfo 命名空间整体健康状态如何？"
user_input = "查看 bookinfo 所有 Pod 的重启次数"
```

---

## 演示示例

### 示例一：多步骤健康检查

**用户输入：**
```
请帮我检查 bookinfo 命名空间的整体运行状况：
1. 首先检查 Prometheus 是否正常运行
2. 查询 bookinfo 下所有 Pod 的 CPU 使用情况
3. 查询 bookinfo 下所有 Pod 的内存使用情况
4. 查询各个 Pod 的重启次数
5. 汇总成一份完整的健康状态报告
```

**智能体执行流程：**

| 步骤 | 工具调用 | 说明 |
|------|---------|------|
| 1 | `prometheus_health_check()` | 验证 Prometheus 可用性 |
| 2 | `query_pod_cpu_usage("bookinfo")` | 查询 CPU 排名 |
| 3 | `query_pod_memory_usage("bookinfo")` | 查询内存排名 |
| 4 | `query_pod_restart_count("bookinfo")` | 查询重启次数 |
| 5 | — | 汇总生成综合健康报告 |

### 示例二：趋势分析与可视化

**用户输入：** `reviews-v2 最近五分钟的 CPU 使用趋势如何？帮我生成趋势图`

**智能体执行：** `query_cpu_trend(namespace="bookinfo", pod_name="reviews-v2", duration_minutes=5, save_chart=True)`

**输出：** 趋势分析文本报告 + `output/charts/cpu_trend_*.png` 折线图

### 示例三：快速问答映射

| 问题 | 智能体调用的工具 |
|------|----------------|
| "现在 bookinfo 各个服务的内存占用情况怎么样？" | `query_pod_memory_usage("bookinfo")` |
| "bookinfo 命名空间整体健康状态如何？" | `query_namespace_health_report("bookinfo")` |
| "查看 bookinfo 所有 Pod 的重启次数" | `query_pod_restart_count("bookinfo")` |
| "productpage 的 CPU 占用是多少" | `query_pod_cpu_usage("bookinfo", "productpage")` |
| "Prometheus 是否正常运行？" | `prometheus_health_check()` |

---

## 工具参考手册

| 工具名称 | 输入参数 | 输出内容 | PromQL 要点 |
|----------|---------|---------|-------------|
| `prometheus_query_tool` | promql, url, use_range, duration, step | 原始查询结果 | 自定义 PromQL |
| `query_pod_cpu_usage` | namespace, pod_name, url | CPU 排名 + 异常检测 | `rate(container_cpu_usage_seconds_total[5m])` |
| `query_pod_memory_usage` | namespace, pod_name, url | 内存排名(MiB) + 预警 | `container_memory_working_set_bytes` |
| `query_pod_restart_count` | namespace, pod_name, url | 重启次数 + 分级告警 | `kube_pod_container_status_restarts_total` |
| `query_namespace_health_report` | namespace, url | 一站式健康报告 | 多 PromQL 聚合 |
| `query_cpu_trend` | namespace, pod_name, duration, save_chart | 趋势分析 + 折线图 | 范围查询 + 分段均值比较 |
| `query_memory_trend` | namespace, pod_name, duration, save_chart | 趋势分析 + 折线图 | 范围查询 + 泄漏检测 |
| `query_pod_network_io` | namespace, pod_name, url | 表格：Pod、Rx、Tx | `rate(container_network_*_bytes_total[5m])` |
| `prometheus_health_check` | url | 版本、状态、Targets | `/api/v1/status/buildinfo` |
| `jaeger_query_tool` | service_name, limit, url | 调用链列表 | Jaeger HTTP API |
| `failure_diagnosis_tool` | failure_msg | 根因分析 + 修复建议 | 基于 LLM 诊断 |

---

## 项目结构

```
ops-agent-lab3/
│
├── main.py                         # 程序入口（智能监控问答助手）
├── requirements.txt                # Python 依赖管理
├── .env                            # API Key 配置（需自行创建）
├── .env.example                    # 环境变量模板
├── README.md                       # 本文档
├── 实验报告.md                     # 完整实验报告
│
├── core/
│   ├── agent_builder.py            # MonitorAgent 构建
│   ├── tools/
│   │   ├── monitor_tools.py        # 10个 Prometheus 监控工具（核心）
│   │   └── failure_tools.py        # 故障诊断工具
│   ├── helper/
│   │   ├── llm_util.py             # LLM 初始化（DeepSeek）
│   │   └── logger.py               # 日志记录器
│   └── prompts/
│       └── ops_agent_prompt.py     # MONITORING_SYSTEM_PROMPT
│
├── output/
│   ├── logs/                       # 运行日志
│   └── charts/                     # 趋势图（PNG）
│
└── test-project/                   # 测试示例项目
```

---

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `DEEPSEEK_API_KEY` 未设置 | 缺少 API Key | 创建 `.env` 文件设置 Key |
| Prometheus 连接被拒绝 | Prometheus 未启动 | 启动 Prometheus 服务 |
| 查询返回空数据 | 指标名不匹配 | 检查 Prometheus Targets 状态 |
| "未找到重启数据" | kube-state-metrics 未部署 | 安装 kube-state-metrics |
| matplotlib 中文乱码 | 缺少中文字体 | 图表使用英文标签 |

---

> **项目地址**：[https://github.com/liulianbuqu/ops-agent-lab3](https://github.com/liulianbuqu/ops-agent-lab3)
>
> **课程**：《软件服务工程》实验三：智能体服务
