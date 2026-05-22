# Ops Agent — 智能运维助手

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-0.3.30-green)](https://langchain.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

基于 **LangChain + DeepSeek** 构建的智能运维助手（Ops Agent），支持通过**自然语言**完成 Kubernetes 集群监控、Docker 容器化部署、Prometheus 指标查询与故障诊断等运维任务。

---

## 📋 目录

- [应用场景](#-应用场景)
- [功能清单](#-功能清单)
- [技术架构](#-技术架构)
- [环境准备](#-环境准备)
- [快速开始](#-快速开始)
- [演示场景](#-演示场景)
  - [场景一：智能监控问答助手](#场景一智能监控问答助手)
  - [场景二：K8s 自动化部署流水线](#场景二k8s-自动化部署流水线)
  - [场景三：故障注入与智能诊断闭环](#场景三故障注入与智能诊断闭环)
- [工具参考手册](#-工具参考手册)
- [项目结构](#-项目结构)
- [常见问题](#-常见问题)

---

## 🎯 应用场景

### 场景一：智能监控问答助手（默认场景）

将 Prometheus 查询能力封装为具有清晰语义的智能体工具，运维人员通过**自然语言**提问即可获取结构化监控报告。

**典型交互：**

```
用户：现在 bookinfo 各个服务的内存占用情况怎么样？

智能体：（自动调用 Prometheus 查询）
  💾 内存使用报告 — 命名空间: bookinfo
  ==================================================
    📦 productpage-v1-xxxxx    内存: 303.2 MiB
    📦 reviews-v1-xxxxx        内存: 152.8 MiB
    📦 reviews-v2-xxxxx        内存: 148.6 MiB
    ...
  ==================================================
    ✅ 所有 Pod 内存使用在正常范围内，无异常。
```

**核心能力：**
- 🖥️ **CPU 监控** — 查询 Pod CPU 使用率，按使用量排名，异常检测
- 💾 **内存监控** — 查询 Pod 内存使用量（MiB），超阈值预警
- 🔄 **重启监控** — 检测 Pod 重启次数，分级告警（🟢/🟡/🔴）
- 🌐 **网络 I/O** — 查询 Pod 网络接收/发送速率
- 📈 **趋势可视化** — 自动生成 matplotlib 折线图，直观展示时序变化
- 📋 **一站式健康报告** — 聚合 CPU + 内存 + 重启，生成命名空间综合评估

### 场景二：K8s 自动化部署流水线

从项目源码到 K8s 集群的完整自动化部署流水线——智能体自主完成 Dockerfile 生成、镜像构建、K8s 资源清单生成与集群发布。

**典型交互：**

```
用户：请将 test-project 部署到 K8s 集群中，暴露 3000 端口，副本数 2。

智能体：开始执行部署流水线...
  步骤 1/6: 读取 README → 分析 Node.js 项目需求
  步骤 2/6: 生成 Dockerfile → 保存到磁盘
  步骤 3/6: docker build → 构建镜像 test-node-app:latest
  步骤 4/6: 生成 Deployment + Service YAML
  步骤 5/6: kubectl apply → 部署到集群
  步骤 6/6: 检查 Pod 状态 → 验证部署成功 ✅
```

### 场景三：故障注入与智能诊断闭环

当用户描述异常现象时，智能体主动调用多种工具收集诊断依据，综合分析后输出根因定位与修复建议。

```
用户：productpage 访问变慢了，帮我排查一下。

智能体：正在诊断，请稍候...
  → 查询 Prometheus CPU/内存 → 无异常
  → 查询 Jaeger Trace → 发现 reviews 调用耗时 3.2s
  → 查询 Pod 日志 → 未发现错误
  → 诊断结论：可能 reviews→ratings 间存在网络延迟
```

---

## ✨ 功能清单

### 🤖 智能体核心
| 功能 | 说明 |
|------|------|
| ReAct 推理循环 | Thought → Action → Observation 自主决策 |
| 24 个预注册工具 | 覆盖文件、Docker、K8s、监控、诊断 |
| 结构化输出 | 工具返回格式化报告，智能体生成分析结论 |
| 故障自诊断 | 出错时自动调用 `failure_diagnosis_tool` 分析根因 |
| 多工具协同 | 自动组合多个工具完成复杂多步骤任务 |

### 📊 监控查询（10 个工具）
| 工具 | 功能 | PromQL 核心 |
|------|------|-------------|
| `prometheus_query_tool` | 通用 PromQL 查询（即时/范围） | 用户自定义 |
| `query_pod_cpu_usage` | Pod CPU 使用率排名 | `rate(container_cpu_usage_seconds_total[5m])` |
| `query_pod_memory_usage` | Pod 内存使用排名（MiB） | `container_memory_working_set_bytes` |
| `query_pod_restart_count` | Pod 重启次数检测 | `kube_pod_container_status_restarts_total` |
| `query_namespace_health_report` | 一站式健康报告 | 多 PromQL 聚合 |
| `query_cpu_trend` | CPU 趋势 + 折线图 | 范围查询 + matplotlib |
| `query_memory_trend` | 内存趋势 + 折线图 | 范围查询 + matplotlib |
| `query_pod_network_io` | 网络接收/发送速率 | `container_network_*_bytes_total` |
| `prometheus_health_check` | Prometheus 健康检查 | `/api/v1/status/buildinfo` |
| `jaeger_query_tool` | Jaeger 调用链查询 | Jaeger HTTP API |

### 🐳 Docker 工具（5 个工具）
| 工具 | 功能 |
|------|------|
| `dockerfile_generate_tool` | 基于 README 用 LLM 生成 Dockerfile |
| `image_build_tool` | 执行 docker build 构建镜像 |
| `container_run_tool` | 运行容器并映射端口 |
| `container_exec_cmd_tool` | 在容器内执行命令 |
| `container_logs_tool` | 查看容器日志 |

### ☸️ Kubernetes 工具（5 个工具）
| 工具 | 功能 |
|------|------|
| `k8s_yaml_generate_tool` | 用 LLM 生成 Deployment + Service YAML |
| `k8s_apply_tool` | 执行 kubectl apply 部署 |
| `k8s_pod_status_tool` | 查询 Pod 状态并统计 |
| `k8s_delete_tool` | 删除 K8s 资源 |
| `k8s_namespace_tool` | 创建/检查命名空间 |

### 🔧 其他工具
| 工具 | 功能 |
|------|------|
| `file_read_tool` | 读取文件内容 |
| `file_write_tool` | 写入文件（自动创建目录） |
| `file_list_tool` | 列出目录文件 |
| `failure_diagnosis_tool` | 基于 LLM 的故障根因分析 |

---

## 🏗 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    用户自然语言输入                        │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  OpsAgent (core/agent_builder.py)                       │
│  ┌────────────────────────────────────────────────────┐ │
│  │  ReAct 循环 (Thought → Action → Observation)       │ │
│  │  LLM: DeepSeek Chat (temperature=0)                │ │
│  │  系统提示词: MONITORING_SYSTEM_PROMPT              │ │
│  └────────────────────────────────────────────────────┘ │
└──────┬──────────┬──────────┬──────────┬─────────────────┘
       │          │          │          │
┌──────▼──┐ ┌─────▼─────┐ ┌─▼────────┐ ┌▼──────────────┐
│ File    │ │ Docker    │ │ K8s      │ │ Monitor       │
│ Tools   │ │ Tools     │ │ Tools    │ │ Tools         │
│ ─────── │ │ ────────  │ │ ─────── │ │ ────────────  │
│ read    │ │ Dockerfile│ │ YAML gen │ │ PromQL 查询    │
│ write   │ │ build     │ │ apply    │ │ CPU/内存/重启  │
│ list    │ │ run/exec  │ │ status   │ │ 趋势可视化     │
└─────────┘ └───────────┘ └──────────┘ │ 健康报告       │
                                       └────────────────┘
```

### 技术栈

| 组件 | 技术选型 | 用途 |
|------|---------|------|
| **LLM** | DeepSeek Chat (OpenAI 兼容 API) | 智能体推理与决策 |
| **Agent 框架** | LangChain 0.3.30 | ReAct 循环、工具绑定、执行器 |
| **监控** | Prometheus + prometheus-api-client | 指标查询与数据获取 |
| **可视化** | matplotlib 3.10 | 趋势折线图生成 |
| **容器** | Docker SDK / docker CLI | 镜像构建与容器管理 |
| **编排** | kubectl CLI | Kubernetes 资源管理 |
| **追踪** | Jaeger HTTP API | 分布式调用链查询 |

---

## 🔧 环境准备

### 前置依赖

| 依赖 | 版本要求 | 用途 |
|------|---------|------|
| Python | ≥ 3.11 | 运行环境 |
| Docker | ≥ 24.0 | 容器化部署（场景二需要） |
| Kubernetes | ≥ 1.28 | 集群部署（场景二需要） |
| Prometheus | ≥ 2.45 | 监控数据源（场景一需要） |
| kubectl | ≥ 1.28 | K8s 集群交互 |

### 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\Activate.ps1    # Windows
source .venv/bin/activate      # Linux/Mac

# 安装所需依赖
pip install -r requirements.txt
```

`requirements.txt` 包含的核心依赖：

```text
langchain==0.3.30
langchain_community==0.3.31
langchain_core==0.3.86
langchain_openai==0.2.14
docker>=7.0.0
kubernetes>=30.0.0
prometheus-api-client>=0.5.0
matplotlib>=3.8.0
pydantic>=2.0.0
python-dotenv>=1.0.0
```

---

## ⚙️ 配置 LLM

### 方式一：创建 `.env` 文件（推荐）

在项目根目录创建 `.env` 文件：

```ini
# DeepSeek API 配置
DEEPSEEK_API_KEY=sk-你的API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

### 方式二：环境变量

```powershell
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-你的API Key"
$env:DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
$env:DEEPSEEK_MODEL = "deepseek-chat"

# Linux/Mac
export DEEPSEEK_API_KEY="sk-你的API Key"
export DEEPSEEK_BASE_URL="https://api.deepseek.com/v1"
export DEEPSEEK_MODEL="deepseek-chat"
```

> **说明**：项目兼容所有兼容 OpenAI API 格式的模型服务（DeepSeek、OpenAI、通义千问等），只需修改 `base_url` 和 `model` 即可。

---

## 🚀 快速开始

### 运行主程序

```bash
# 激活虚拟环境后
python main.py
```

主程序默认执行**场景一：智能监控问答助手**，查询 `bookinfo` 命名空间的整体运行状况。

### 切换演示场景

编辑 `main.py`，在 `# ===== 用户输入 =====` 区域选择不同的 `user_input`：

```python
# ===== 场景一：智能监控问答（默认） =====
user_input = """请帮我检查 bookinfo 命名空间的整体运行状况：
1. 首先检查 Prometheus 是否正常运行
2. 查询 bookinfo 下所有 Pod 的 CPU 使用情况
3. 查询 bookinfo 下所有 Pod 的内存使用情况
4. 查询各个 Pod 的重启次数
5. 汇总成一份完整的健康状态报告
"""

# ===== 场景一：趋势可视化 =====
# user_input = "reviews-v2 最近五分钟的 CPU 使用趋势如何？"

# ===== 场景一：快速问答 =====
# user_input = "现在 bookinfo 各个服务的内存占用情况怎么样？"

# ===== 场景二：K8s 部署流水线 =====
# user_input = """请帮我完成以下任务：
# 1. 读取 test-project/README.md 的内容，分析项目需求
# 2. 根据项目需求生成 Dockerfile 并保存到 test-project/ 目录中
# 3. 使用该 Dockerfile 构建 Docker 镜像，标签为 test-node-app:latest
# 4. 运行一个容器（容器名 my-test-app），将容器的 3000 端口映射到 8080
# 5. 访问 http://localhost:8080 验证服务是否正常运行
# """
```

---

## 🎬 演示场景

### 场景一：智能监控问答助手

> **前置条件**：需要运行中的 Kubernetes 集群（如 Minikube）、已部署 Prometheus 和 Istio bookinfo 示例应用。

#### 演示 1：多步骤健康检查

**用户输入：**
```
请帮我检查 bookinfo 命名空间的整体运行状况：
1. 首先检查 Prometheus 是否正常运行
2. 查询 bookinfo 下所有 Pod 的 CPU 使用情况
3. 查询 bookinfo 下所有 Pod 的内存使用情况
4. 查询各个 Pod 的重启次数
5. 汇总成一份完整的健康状态报告
```

**智能体行为：**
```
Step 1 → prometheus_health_check()          → Prometheus running ✅
Step 2 → query_pod_cpu_usage("bookinfo")    → CPU 排名数据
Step 3 → query_pod_memory_usage("bookinfo") → 内存排名数据
Step 4 → query_pod_restart_count("bookinfo") → 重启统计数据
Step 5 → 汇总生成综合健康报告
```

**预期输出：**
```
📋 命名空间健康报告 — bookinfo
============================================================
  报告时间: 2026-05-22 11:20:00

🔥 【CPU 使用率】
  📦 productpage-v1-xxxxx: 0.035 cores
  📦 reviews-v1-xxxxx: 0.012 cores
  ...

💾 【内存使用】
  📦 productpage-v1-xxxxx: 303.2 MiB
  📦 details-v1-xxxxx: 54.3 MiB
  ...

🔄 【Pod 重启次数】
  🟢 productpage-v1-xxxxx: 0 次
  🟢 details-v1-xxxxx: 0 次
  ...

📊 【综合评估】
  ✅ 命名空间整体运行正常，无异常情况。
```

#### 演示 2：趋势分析与可视化

**用户输入：**
```
reviews-v2 最近五分钟的 CPU 使用趋势如何？
```

**智能体行为：**
```
→ query_cpu_trend(namespace="bookinfo", pod_name="reviews-v2",
    duration_minutes=5, save_chart=True)
```

**预期输出：**
```
📈 CPU 使用趋势报告
==================================================
  命名空间: bookinfo, Pod: reviews-v2
  时间范围: 最近 5 分钟
==================================================
  📦 reviews-v2-xxxxx
      最新: 0.023 cores
      平均: 0.021 cores
      最高: 0.035 cores
      最低: 0.015 cores
      ➡️ 趋势: 平稳（+3.2%）

📊 CPU 趋势图已保存至: output/charts/cpu_trend_bookinfo_reviews-v2_20260522_112000.png
```

同时会在 `output/charts/` 目录下生成 matplotlib 折线图。

#### 演示 3：快速问答

| 问题 | 智能体会调用的工具 |
|------|-------------------|
| "现在 bookinfo 各个服务的内存占用情况怎么样？" | `query_pod_memory_usage("bookinfo")` |
| "reviews-v2 最近五分钟的 CPU 使用趋势如何？" | `query_cpu_trend("bookinfo", "reviews-v2", 5)` |
| "bookinfo 命名空间整体健康状态如何？" | `query_namespace_health_report("bookinfo")` |
| "查看 bookinfo 所有 Pod 的重启次数" | `query_pod_restart_count("bookinfo")` |
| "Prometheus 是否正常运行？" | `prometheus_health_check()` |
| "查看 productpage 服务的调用链" | `jaeger_query_tool("productpage")` |
| "查看 bookinfo 各服务的网络流量" | `query_pod_network_io("bookinfo")` |

### 场景二：K8s 自动化部署流水线

> **前置条件**：需要安装 Docker Desktop 或 Docker Engine。

**用户输入：**
```
请帮我完成以下任务：
1. 读取 test-project/README.md 的内容，分析项目需求
2. 根据项目需求生成 Dockerfile 并保存到 test-project/ 目录中
3. 使用该 Dockerfile 构建 Docker 镜像，标签为 test-node-app:latest
4. 运行一个容器（容器名 my-test-app），将容器的 3000 端口映射到宿主机的 8080 端口
5. 访问 http://localhost:8080 验证服务是否正常运行
```

**智能体完整工作流：**
```
Thought: 用户需要一个完整的部署流水线，我按步骤执行。
Action: file_read_tool("test-project/README.md")
Observation: Node.js 项目，监听 3000 端口，返回 Hello World

Thought: 用 LLM 生成 Dockerfile
Action: dockerfile_generate_tool(...)
Observation: Dockerfile 已保存

Thought: 构建 Docker 镜像
Action: image_build_tool(...)
Observation: 镜像构建成功

Thought: 运行容器
Action: container_run_tool(image="test-node-app:latest", ...)
Observation: 容器已启动，访问 http://localhost:8080

Thought: 验证服务
Action: container_exec_cmd_tool("my-test-app", "curl localhost:3000")
Observation: Hello World ✅
```

### 场景三：故障诊断

当工具返回错误时，智能体会自动调用 `failure_diagnosis_tool` 进行诊断。例如：

```
Action: image_build_tool(...)
Observation: 错误: npm ci 失败，缺少 package-lock.json

Thought: 构建失败，调用故障诊断工具
Action: failure_diagnosis_tool("npm ci failed...")
Observation: 根因: 缺少 lockfile。修复: 修改 Dockerfile 用 npm install 替代 npm ci

Thought: 修改 Dockerfile 重试...
```

---

## 📚 工具参考手册

### 监控工具（10个）

| 工具名称 | 输入参数 | 输出内容 | PromQL 要点 |
|----------|---------|---------|-------------|
| `prometheus_query_tool` | promql, url, use_range, duration, step | 原始查询结果 | 用户自定义 |
| `query_pod_cpu_usage` | namespace, pod_name, url | CPU 排名 + 异常检测 | `rate(container_cpu_usage_seconds_total[5m])` |
| `query_pod_memory_usage` | namespace, pod_name, url | 内存排名(MiB) + 预警 | `container_memory_working_set_bytes` |
| `query_pod_restart_count` | namespace, pod_name, url | 重启次数 + 分级告警 | `kube_pod_container_status_restarts_total` |
| `query_namespace_health_report` | namespace, url | 一站式健康报告 | 多 PromQL 聚合 |
| `query_cpu_trend` | namespace, pod_name, duration, step, url, save_chart | 趋势分析 + 折线图 | 范围查询 + 分段比较 |
| `query_memory_trend` | namespace, pod_name, duration, step, url, save_chart | 趋势分析 + 折线图 | 范围查询 + 泄漏检测 |
| `query_pod_network_io` | namespace, pod_name, url | 表格：Pod、Rx、Tx | `rate(container_network_*_bytes_total[5m])` |
| `prometheus_health_check` | url | 版本、状态、Targets | `/api/v1/status/buildinfo` |
| `jaeger_query_tool` | service_name, limit, url | 调用链列表或服务列表 | Jaeger HTTP API |

### Docker 工具（5个）

| 工具名称 | 功能 | 关键参数 |
|----------|------|---------|
| `dockerfile_generate_tool` | LLM 生成 Dockerfile | readme_path, project_path, save_path |
| `image_build_tool` | 构建镜像 | docker_file_path, image_tag |
| `container_run_tool` | 运行容器 | image_tag, container_name, internal_port, expose_port |
| `container_exec_cmd_tool` | 容器内执行命令 | container_name, command |
| `container_logs_tool` | 查看容器日志 | container_name, tail |

### Kubernetes 工具（5个）

| 工具名称 | 功能 | 关键参数 |
|----------|------|---------|
| `k8s_yaml_generate_tool` | LLM 生成 Deployment+Service YAML | service_name, image, container_port, replicas, namespace |
| `k8s_apply_tool` | 部署到集群 | yaml_file_path |
| `k8s_pod_status_tool` | 查询 Pod 状态 | namespace, label_selector |
| `k8s_delete_tool` | 删除资源 | yaml_file_path / resource_type + resource_name |
| `k8s_namespace_tool` | 管理命名空间 | namespace, action(create/check) |

### 其他工具（4个）

| 工具名称 | 功能 | 关键参数 |
|----------|------|---------|
| `file_read_tool` | 读取文件 | file_path |
| `file_write_tool` | 写入文件 | content, file_path |
| `file_list_tool` | 列出目录 | directory_path |
| `failure_diagnosis_tool` | 故障诊断 | failure_msg |

---

## 📁 项目结构

```
ops-agent-lab3/
│
├── main.py                         # 🚀 程序入口（默认场景：智能监控问答）
├── requirements.txt                # 📦 Python 依赖
├── .env                            # 🔑 API 密钥配置（需自行创建）
├── .env.example                    # 📄 环境变量模板
├── .gitignore                      # 🙈 Git 忽略规则
├── README.md                       # 📖 本文档
├── 实验报告.md                     # 📝 完整实验报告
│
├── core/                           # 🧠 核心代码
│   ├── agent_builder.py            #   OpsAgent 构建（含 MONITORING_SYSTEM_PROMPT）
│   │
│   ├── tools/                      # 🔧 工具层（24个工具）
│   │   ├── monitor_tools.py        #   📊 10个Prometheus监控工具
│   │   ├── docker_tools.py         #   🐳 5个Docker工具
│   │   ├── k8s_tools.py            #   ☸️ 5个K8s工具
│   │   ├── file_tools.py           #   📁 3个文件工具
│   │   └── failure_tools.py        #   🩺 故障诊断工具
│   │
│   ├── helper/                     # 🛠️ 辅助模块
│   │   ├── llm_util.py             #   LLM 初始化（DeepSeek/OpenAI）
│   │   └── logger.py               #   日志记录器
│   │
│   └── prompts/                    # 💬 提示词工程
│       ├── ops_agent_prompt.py     #   MONITORING_SYSTEM_PROMPT
│       └── dockerfile_prompt.py    #   Dockerfile 生成提示词
│
├── output/                         # 📂 输出目录
│   ├── logs/                       #   📋 运行日志
│   └── charts/                     #   📊 趋势分析图表（PNG）
│
└── test-project/                   # 🧪 测试示例项目
    ├── README.md                   #   项目需求描述
    ├── package.json                #   Node.js 配置
    ├── app.js                      #   "Hello World" 应用
    ├── Dockerfile                  #   预生成的 Dockerfile
    └── k8s-deployment.yaml         #   预生成的 K8s YAML
```

---

## ⚠️ 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `DEEPSEEK_API_KEY` 未设置 | 缺少 API Key 配置 | 创建 `.env` 文件，设置 `DEEPSEEK_API_KEY=sk-...` |
| Prometheus 查询空数据 | Prometheus 未运行或指标名不匹配 | 启动 Prometheus，检查 Targets 是否正常采集 |
| Prometheus 连接被拒绝 | Prometheus 服务未启动 | `prometheus_health_check()` 诊断，启动 Prometheus |
| kubectl 连接失败 | K8s 集群未运行或上下文错误 | 启动 Minikube/kind，配置 `kubectl config use-context` |
| Docker 命令未找到 | Docker 未安装或 PATH 缺失 | 安装 Docker Desktop，确保 docker 命令可用 |
| matplotlib 中文乱码 | 系统中文字体缺失 | 图表使用英文标签，或安装中文字体 |
| LangChain 弃用警告 | LangChain 推荐迁移到 LangGraph | 当前版本仍可用，不影响功能 |

---

## 📄 许可

本项目为《软件服务工程》课程实验作业，仅供学习参考。

---

> **项目地址**：[https://github.com/liulianbuqu/ops-agent-lab3](https://github.com/liulianbuqu/ops-agent-lab3)
>
> **技术栈**：Python 3.11+ · LangChain 0.3.30 · DeepSeek Chat · Prometheus · Docker · Kubernetes · matplotlib
