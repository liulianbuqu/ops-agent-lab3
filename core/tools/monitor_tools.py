"""
监控与可观测性工具
包括 Prometheus 指标查询、趋势可视化、Pod 资源排名、健康检查等
支持通过自然语言驱动，自动选择合适的 PromQL 并生成可读分析报告。
"""
import os
import datetime
import json
from typing import Optional
from langchain_core.tools import tool

# ============================================================
# 辅助函数
# ============================================================

DIAGNOSIS_SUGGESTION = (
    "\n\n[提示] 如果上述输出包含错误信息，"
    "建议调用 failure_diagnosis_tool 进行故障分析。"
)


def _get_prometheus_client(prometheus_url: str = "http://localhost:9090"):
    """创建并返回 PrometheusConnect 客户端实例。"""
    from prometheus_api_client import PrometheusConnect
    return PrometheusConnect(url=prometheus_url, disable_ssl=True)


def _format_bytes_to_mib(bytes_value: float) -> str:
    """将字节转换为 MiB 并格式化。"""
    mib = bytes_value / (1024 * 1024)
    return f"{mib:.1f} MiB"


def _format_bytes_to_gib(bytes_value: float) -> str:
    """将字节转换为 GiB 并格式化。"""
    gib = bytes_value / (1024 * 1024 * 1024)
    return f"{gib:.2f} GiB"


def _format_cpu_cores(cpu_value: float) -> str:
    """将 CPU 核心数格式化为可读字符串。"""
    if cpu_value < 0.01:
        return f"{cpu_value * 1000:.2f} m"
    return f"{cpu_value:.3f} cores"


def _parse_instant_query_result(result: list) -> list:
    """解析 Prometheus 即时查询结果，返回结构化的字典列表。"""
    parsed = []
    for item in result:
        metric = item.get("metric", {})
        value = item.get("value", [])
        val = float(value[1]) if value and len(value) > 1 else 0.0
        parsed.append({
            "metric": metric,
            "value": val,
            "labels": {k: v for k, v in metric.items()}
        })
    return parsed


def _parse_range_query_result(result: list) -> list:
    """解析 Prometheus 范围查询结果，返回结构化的字典列表（含时序数据）。"""
    parsed = []
    for item in result:
        metric = item.get("metric", {})
        values = item.get("values", [])
        data_points = [(ts, float(v)) for ts, v in values] if values else []
        latest_value = data_points[-1][1] if data_points else 0.0
        parsed.append({
            "metric": metric,
            "values": data_points,
            "latest_value": latest_value,
            "labels": {k: v for k, v in metric.items()}
        })
    return parsed


# ============================================================
# 工具 1: 通用 PromQL 查询工具（底层）
# ============================================================

@tool("prometheus_query_tool")
def prometheus_query_tool(
    promql: str,
    prometheus_url: str = "http://localhost:9090",
    use_range: bool = False,
    duration_minutes: int = 5,
    step_seconds: int = 15
) -> str:
    """
    Execute a raw PromQL query against Prometheus. Use this when you need a custom query that
    doesn't fit the other specialized tools.

    Args:
        promql: The PromQL query string.
        prometheus_url: Prometheus server base URL (default: http://localhost:9090).
        use_range: If True, performs a range query over the last N minutes.
        duration_minutes: Time range in minutes for range queries (default: 5).
        step_seconds: Step interval in seconds for range queries (default: 15).
    """
    try:
        prom = _get_prometheus_client(prometheus_url)

        if use_range:
            end_time = datetime.datetime.now()
            start_time = end_time - datetime.timedelta(minutes=duration_minutes)
            result = prom.custom_query_range(
                query=promql,
                start_time=start_time,
                end_time=end_time,
                step=step_seconds
            )
        else:
            result = prom.custom_query(query=promql)

        if not result:
            return f"PromQL 查询已执行，但未返回数据。\n查询: {promql}"

        output_lines = [f"📊 PromQL: `{promql}`", f"结果数量: {len(result)}", ""]
        for item in result[:20]:
            metric = item.get("metric", {})
            metric_str = ", ".join(f"{k}={v}" for k, v in metric.items())

            if use_range:
                values = item.get("values", [])
                if values:
                    latest_value = values[-1][1]
                    output_lines.append(f"  Metric: {{{metric_str}}}")
                    output_lines.append(f"  最新值: {latest_value}")
                    output_lines.append(f"  数据点: {len(values)}")
            else:
                value = item.get("value", [])
                if value and len(value) > 1:
                    output_lines.append(f"  Metric: {{{metric_str}}}")
                    output_lines.append(f"  值: {value[1]}")
            output_lines.append("")

        return "\n".join(output_lines)

    except ImportError:
        return "错误: 未安装 prometheus-api-client 库。请执行: pip install prometheus-api-client"
    except Exception as e:
        return f"Prometheus 查询失败: {str(e)}" + DIAGNOSIS_SUGGESTION


# ============================================================
# 工具 2: Pod CPU 使用率查询
# ============================================================

@tool("query_pod_cpu_usage")
def query_pod_cpu_usage(
    namespace: str = "default",
    pod_name: str = "",
    prometheus_url: str = "http://localhost:9090"
) -> str:
    """
    【CPU 监控】查询指定 namespace 下所有 Pod（或特定 Pod）的 CPU 使用率。
    返回每个 Pod 的 CPU 占用（cores 和 millicores），按使用量降序排列。
    典型提问："查看 bookinfo 各服务的 CPU 使用情况"、"productpage 的 CPU 占用是多少"

    Args:
        namespace: Kubernetes 命名空间（默认: default）。
        pod_name: 可选，特定 Pod 名称前缀（如 reviews-v2），为空则查全部。
        prometheus_url: Prometheus 服务地址。
    """
    try:
        prom = _get_prometheus_client(prometheus_url)

        if pod_name:
            promql = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod=~".*{pod_name}.*"}}[5m])) by (pod)'
        else:
            promql = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m])) by (pod)'

        result = prom.custom_query(query=promql)
        parsed = _parse_instant_query_result(result)
        parsed.sort(key=lambda x: x["value"], reverse=True)

        if not parsed:
            return f"在命名空间 '{namespace}' 中未找到 CPU 数据。"

        lines = [
            f"🔥 CPU 使用率报告 — 命名空间: {namespace}",
            f"{'='*50}"
        ]

        for p in parsed:
            pod = p["labels"].get("pod", "unknown")
            cpu_val = p["value"]
            lines.append(f"  📦 {pod}")
            lines.append(f"     CPU: {_format_cpu_cores(cpu_val)}")
            lines.append("")

        # 汇总
        total_cpu = sum(p["value"] for p in parsed)
        lines.append(f"{'='*50}")
        lines.append(f"  📈 总计 CPU 使用: {_format_cpu_cores(total_cpu)}")
        lines.append(f"  📊 服务数量: {len(parsed)}")

        # 分析结论
        max_pod = parsed[0]
        lines.append(f"\n💡 分析: {max_pod['labels'].get('pod', 'unknown')} 的 CPU 占用最高"
                     f"（{_format_cpu_cores(max_pod['value'])}），"
                     f"占整体的 {max_pod['value']/total_cpu*100:.1f}%。")

        # 判断是否异常
        avg_cpu = total_cpu / len(parsed)
        abnormal = [p for p in parsed if p["value"] > avg_cpu * 3]
        if abnormal:
            for p in abnormal:
                lines.append(f"⚠️  {p['labels'].get('pod', 'unknown')} CPU 使用显著高于平均水平，建议关注。")

        return "\n".join(lines)

    except ImportError:
        return "错误: 未安装 prometheus-api-client 库。"
    except Exception as e:
        return f"CPU 查询失败: {str(e)}" + DIAGNOSIS_SUGGESTION


# ============================================================
# 工具 3: Pod 内存使用量查询
# ============================================================

@tool("query_pod_memory_usage")
def query_pod_memory_usage(
    namespace: str = "default",
    pod_name: str = "",
    prometheus_url: str = "http://localhost:9090"
) -> str:
    """
    【内存监控】查询指定 namespace 下所有 Pod（或特定 Pod）的内存使用量。
    返回每个 Pod 的内存占用（字节/MiB），按使用量降序排列。
    典型提问："bookinfo 各服务的内存占用情况"、"reviews-v2 内存用了多少"

    Args:
        namespace: Kubernetes 命名空间（默认: default）。
        pod_name: 可选，特定 Pod 名称前缀，为空则查全部。
        prometheus_url: Prometheus 服务地址。
    """
    try:
        prom = _get_prometheus_client(prometheus_url)

        if pod_name:
            promql = f'sum(container_memory_working_set_bytes{{namespace="{namespace}",pod=~".*{pod_name}.*",container!=""}}) by (pod)'
        else:
            promql = f'sum(container_memory_working_set_bytes{{namespace="{namespace}",container!=""}}) by (pod)'

        result = prom.custom_query(query=promql)
        parsed = _parse_instant_query_result(result)
        parsed.sort(key=lambda x: x["value"], reverse=True)

        if not parsed:
            return f"在命名空间 '{namespace}' 中未找到内存数据。"

        lines = [
            f"💾 内存使用报告 — 命名空间: {namespace}",
            f"{'='*50}"
        ]

        for p in parsed:
            pod = p["labels"].get("pod", "unknown")
            mem_bytes = p["value"]
            lines.append(f"  📦 {pod}")
            lines.append(f"     内存: {_format_bytes_to_mib(mem_bytes)}")
            lines.append("")

        # 汇总
        total_mem = sum(p["value"] for p in parsed)
        lines.append(f"{'='*50}")
        lines.append(f"  📈 总计内存使用: {_format_bytes_to_mib(total_mem)}")
        lines.append(f"  📊 服务数量: {len(parsed)}")

        # 分析结论
        max_pod = parsed[0]
        max_name = max_pod["labels"].get("pod", "unknown")
        lines.append(f"\n💡 分析: {max_name} 内存占用最高"
                     f"（{_format_bytes_to_mib(max_pod['value'])}），"
                     f"占整体的 {max_pod['value']/total_mem*100:.1f}%。")

        # 判断是否正常（超过 1GiB 预警）
        high_mem = [p for p in parsed if p["value"] > 1024 * 1024 * 1024]
        if high_mem:
            for p in high_mem:
                lines.append(f"⚠️  {p['labels'].get('pod', 'unknown')} 内存使用超过 1 GiB，建议关注。")
        else:
            lines.append("✅ 所有 Pod 内存使用在正常范围内，无异常。")

        return "\n".join(lines)

    except ImportError:
        return "错误: 未安装 prometheus-api-client 库。"
    except Exception as e:
        return f"内存查询失败: {str(e)}" + DIAGNOSIS_SUGGESTION


# ============================================================
# 工具 4: Pod 重启次数查询
# ============================================================

@tool("query_pod_restart_count")
def query_pod_restart_count(
    namespace: str = "default",
    pod_name: str = "",
    prometheus_url: str = "http://localhost:9090"
) -> str:
    """
    【重启监控】查询指定 namespace 下所有 Pod（或特定 Pod）的重启次数。
    用于判断服务是否频繁崩溃。
    典型提问："查看 bookinfo 各 Pod 的重启情况"、"哪些 Pod 有异常重启"

    Args:
        namespace: Kubernetes 命名空间（默认: default）。
        pod_name: 可选，特定 Pod 名称前缀。
        prometheus_url: Prometheus 服务地址。
    """
    try:
        prom = _get_prometheus_client(prometheus_url)

        if pod_name:
            promql = f'sum(kube_pod_container_status_restarts_total{{namespace="{namespace}",pod=~".*{pod_name}.*"}}) by (pod)'
        else:
            promql = f'sum(kube_pod_container_status_restarts_total{{namespace="{namespace}"}}) by (pod)'

        result = prom.custom_query(query=promql)
        parsed = _parse_instant_query_result(result)
        parsed.sort(key=lambda x: x["value"], reverse=True)

        if not parsed:
            return f"在命名空间 '{namespace}' 中未找到重启数据（可能 kube-state-metrics 未部署）。"

        lines = [
            f"🔄 Pod 重启次数报告 — 命名空间: {namespace}",
            f"{'='*50}"
        ]

        total_restarts = 0
        abnormal_pods = []

        for p in parsed:
            pod = p["labels"].get("pod", "unknown")
            restarts = int(p["value"])
            total_restarts += restarts
            icon = "🟢" if restarts == 0 else ("🟡" if restarts < 3 else "🔴")
            lines.append(f"  {icon} {pod}")
            lines.append(f"     重启次数: {restarts}")
            if restarts >= 3:
                abnormal_pods.append(pod)
            lines.append("")

        lines.append(f"{'='*50}")
        lines.append(f"  📈 总计重启次数: {total_restarts}")

        if abnormal_pods:
            lines.append(f"\n❌ 异常 Pod（重启 ≥3 次）:")
            for ap in abnormal_pods:
                lines.append(f"  ⚠️  {ap} — 建议立即检查日志并排查根因。")
        else:
            lines.append("\n✅ 所有 Pod 运行稳定，无频繁重启情况。")

        return "\n".join(lines)

    except ImportError:
        return "错误: 未安装 prometheus-api-client 库。"
    except Exception as e:
        return f"重启次数查询失败: {str(e)}" + DIAGNOSIS_SUGGESTION


# ============================================================
# 工具 5: 命名空间资源总览（一站式健康报告）
# ============================================================

@tool("query_namespace_health_report")
def query_namespace_health_report(
    namespace: str = "bookinfo",
    prometheus_url: str = "http://localhost:9090"
) -> str:
    """
    【健康总览】一站式查询指定 namespace 的健康状况，包括：
    - Pod 状态概览（总数、Running、异常数）
    - CPU 使用率排名
    - 内存使用排名
    - Pod 重启次数
    - 整体健康评估结论
    典型提问："bookinfo 命名空间整体健康状态如何"、"查看 bookinfo 的运维报告"

    Args:
        namespace: Kubernetes 命名空间（默认: bookinfo）。
        prometheus_url: Prometheus 服务地址。
    """
    try:
        prom = _get_prometheus_client(prometheus_url)
        report_lines = [
            f"\n{'='*60}",
            f"  📋 命名空间健康报告 — {namespace}",
            f"{'='*60}",
            f"  报告时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"{'='*60}",
        ]

        # ---- 1. CPU ----
        report_lines.append(f"\n🔥 【CPU 使用率】")
        cpu_promql = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m])) by (pod)'
        cpu_result = prom.custom_query(query=cpu_promql)
        cpu_parsed = _parse_instant_query_result(cpu_result)
        cpu_parsed.sort(key=lambda x: x["value"], reverse=True)

        if cpu_parsed:
            for p in cpu_parsed:
                pod = p["labels"].get("pod", "unknown")
                report_lines.append(f"  📦 {pod}: {_format_cpu_cores(p['value'])}")
        else:
            report_lines.append("  (无数据)")

        # ---- 2. 内存 ----
        report_lines.append(f"\n💾 【内存使用】")
        mem_promql = f'sum(container_memory_working_set_bytes{{namespace="{namespace}",container!=""}}) by (pod)'
        mem_result = prom.custom_query(query=mem_promql)
        mem_parsed = _parse_instant_query_result(mem_result)
        mem_parsed.sort(key=lambda x: x["value"], reverse=True)

        if mem_parsed:
            for p in mem_parsed:
                pod = p["labels"].get("pod", "unknown")
                report_lines.append(f"  📦 {pod}: {_format_bytes_to_mib(p['value'])}")
        else:
            report_lines.append("  (无数据)")

        # ---- 3. 重启次数 ----
        report_lines.append(f"\n🔄 【Pod 重启次数】")
        restart_promql = f'sum(kube_pod_container_status_restarts_total{{namespace="{namespace}"}}) by (pod)'
        try:
            restart_result = prom.custom_query(query=restart_promql)
            restart_parsed = _parse_instant_query_result(restart_result)
            if restart_parsed:
                total_restarts = sum(p["value"] for p in restart_parsed)
                for p in restart_parsed:
                    pod = p["labels"].get("pod", "unknown")
                    icon = "🟢" if p["value"] == 0 else "🟡"
                    report_lines.append(f"  {icon} {pod}: {int(p['value'])} 次")
                report_lines.append(f"  → 总计重启: {int(total_restarts)} 次")
            else:
                report_lines.append("  (无数据)")
        except Exception:
            report_lines.append("  (kube-state-metrics 可能未部署)")

        # ---- 4. 综合评估 ----
        report_lines.append(f"\n📊 【综合评估】")
        issues = []

        # CPU 异常检查
        if cpu_parsed:
            avg_cpu = sum(p["value"] for p in cpu_parsed) / len(cpu_parsed)
            for p in cpu_parsed:
                if p["value"] > avg_cpu * 3:
                    issues.append(f"⚠️  {p['labels'].get('pod', '')} CPU 使用异常偏高")

        # 内存异常检查
        if mem_parsed:
            for p in mem_parsed:
                if p["value"] > 1024 * 1024 * 1024:
                    issues.append(f"⚠️  {p['labels'].get('pod', '')} 内存使用超过 1 GiB")

        # 重启检查
        if restart_parsed:
            for p in restart_parsed:
                if p["value"] >= 3:
                    issues.append(f"❌ {p['labels'].get('pod', '')} 频繁重启（{int(p['value'])} 次）")

        if issues:
            report_lines.append("  发现以下问题:")
            for issue in issues:
                report_lines.append(f"  {issue}")
        else:
            report_lines.append("  ✅ 命名空间整体运行正常，无异常情况。")

        report_lines.append(f"{'='*60}\n")
        return "\n".join(report_lines)

    except ImportError:
        return "错误: 未安装 prometheus-api-client 库。"
    except Exception as e:
        return f"健康报告生成失败: {str(e)}" + DIAGNOSIS_SUGGESTION


# ============================================================
# 工具 6: CPU 趋势查询（含可视化）
# ============================================================

@tool("query_cpu_trend")
def query_cpu_trend(
    namespace: str = "default",
    pod_name: str = "",
    duration_minutes: int = 30,
    step_seconds: int = 30,
    prometheus_url: str = "http://localhost:9090",
    save_chart: bool = True
) -> str:
    """
    【CPU 趋势】查询指定 Pod 或命名空间下所有 Pod 的 CPU 使用率时序趋势。
    当 save_chart=True 时会自动生成折线图并保存到 output/charts/ 目录。
    典型提问："reviews-v2 最近五分钟的 CPU 使用趋势"、"bookinfo CPU 趋势图"

    Args:
        namespace: Kubernetes 命名空间。
        pod_name: 可选，特定 Pod 名称前缀，为空则查全部。
        duration_minutes: 查询的时间范围（分钟），默认 30 分钟。
        step_seconds: 数据采样间隔（秒）。
        prometheus_url: Prometheus 服务地址。
        save_chart: 是否自动保存趋势折线图到 output/charts/。
    """
    try:
        prom = _get_prometheus_client(prometheus_url)
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(minutes=duration_minutes)

        if pod_name:
            promql = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod=~".*{pod_name}.*"}}[1m])) by (pod)'
        else:
            promql = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[1m])) by (pod)'

        result = prom.custom_query_range(
            query=promql,
            start_time=start_time,
            end_time=end_time,
            step=step_seconds
        )

        if not result:
            return f"未找到 CPU 趋势数据（namespace={namespace}, pod={pod_name}）。"

        parsed = _parse_range_query_result(result)

        # 生成文本报告
        lines = [
            f"📈 CPU 使用趋势报告",
            f"{'='*50}",
            f"  命名空间: {namespace}" + (f", Pod: {pod_name}" if pod_name else ""),
            f"  时间范围: 最近 {duration_minutes} 分钟",
            f"  采样间隔: {step_seconds}s",
            f"{'='*50}",
        ]

        for p in parsed:
            pod = p["labels"].get("pod", "unknown")
            vals = [v for _, v in p["values"]]
            if not vals:
                continue
            avg_val = sum(vals) / len(vals)
            max_val = max(vals)
            min_val = min(vals)
            latest = vals[-1]

            lines.append(f"\n  📦 {pod}")
            lines.append(f"     最新: {_format_cpu_cores(latest)}")
            lines.append(f"     平均: {_format_cpu_cores(avg_val)}")
            lines.append(f"     最高: {_format_cpu_cores(max_val)}")
            lines.append(f"     最低: {_format_cpu_cores(min_val)}")

            # 趋势判断
            if len(vals) >= 5:
                first_half = sum(vals[:len(vals)//2]) / max(len(vals)//2, 1)
                second_half = sum(vals[len(vals)//2:]) / max(len(vals) - len(vals)//2, 1)
                change = (second_half - first_half) / max(first_half, 0.0001) * 100
                if change > 20:
                    lines.append(f"     📈 趋势: 显著上升（+{change:.1f}%）")
                elif change < -20:
                    lines.append(f"     📉 趋势: 显著下降（{change:.1f}%）")
                else:
                    lines.append(f"     ➡️ 趋势: 平稳（{change:+.1f}%）")

        # 生成可视化图表
        if save_chart:
            try:
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
                import matplotlib.dates as mdates
                import numpy as np

                chart_dir = "./output/charts"
                os.makedirs(chart_dir, exist_ok=True)

                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                pod_label = pod_name if pod_name else "all"
                chart_path = os.path.join(chart_dir, f"cpu_trend_{namespace}_{pod_label}_{timestamp}.png")

                fig, ax = plt.subplots(figsize=(12, 6))

                colors = plt.cm.tab10(np.linspace(0, 1, len(parsed)))

                for idx, p in enumerate(parsed):
                    pod = p["labels"].get("pod", "unknown")
                    if not p["values"]:
                        continue
                    times = [datetime.datetime.fromtimestamp(ts) for ts, _ in p["values"]]
                    vals = [v for _, v in p["values"]]
                    ax.plot(times, vals, marker='o', linestyle='-', linewidth=1.5,
                           markersize=3, label=pod, color=colors[idx % len(colors)])

                ax.set_xlabel('时间', fontsize=12)
                ax.set_ylabel('CPU 使用率 (cores)', fontsize=12)
                ax.set_title(f'CPU 使用趋势 — {namespace}' + (f' / {pod_name}' if pod_name else ''), fontsize=14)
                ax.legend(loc='best', fontsize=10)
                ax.grid(True, alpha=0.3)
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

                plt.tight_layout()
                plt.savefig(chart_path, dpi=150)
                plt.close()

                lines.append(f"\n📊 CPU 趋势图已保存至: {chart_path}")
            except Exception as chart_err:
                lines.append(f"\n⚠️ 图表生成失败: {str(chart_err)}")

        return "\n".join(lines)

    except ImportError:
        return "错误: 未安装 prometheus-api-client 库。"
    except Exception as e:
        return f"CPU 趋势查询失败: {str(e)}" + DIAGNOSIS_SUGGESTION


# ============================================================
# 工具 7: 内存趋势查询（含可视化）
# ============================================================

@tool("query_memory_trend")
def query_memory_trend(
    namespace: str = "default",
    pod_name: str = "",
    duration_minutes: int = 30,
    step_seconds: int = 30,
    prometheus_url: str = "http://localhost:9090",
    save_chart: bool = True
) -> str:
    """
    【内存趋势】查询指定 Pod 或命名空间下所有 Pod 的内存使用量时序趋势。
    当 save_chart=True 时会自动生成折线图并保存到 output/charts/ 目录。
    典型提问："bookinfo 各服务的内存变化趋势"、"productpage 内存趋势图"

    Args:
        namespace: Kubernetes 命名空间。
        pod_name: 可选，特定 Pod 名称前缀。
        duration_minutes: 查询的时间范围（分钟），默认 30 分钟。
        step_seconds: 数据采样间隔（秒）。
        prometheus_url: Prometheus 服务地址。
        save_chart: 是否自动保存趋势折线图。
    """
    try:
        prom = _get_prometheus_client(prometheus_url)
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(minutes=duration_minutes)

        if pod_name:
            promql = f'sum(container_memory_working_set_bytes{{namespace="{namespace}",pod=~".*{pod_name}.*",container!=""}}) by (pod)'
        else:
            promql = f'sum(container_memory_working_set_bytes{{namespace="{namespace}",container!=""}}) by (pod)'

        result = prom.custom_query_range(
            query=promql,
            start_time=start_time,
            end_time=end_time,
            step=step_seconds
        )

        if not result:
            return f"未找到内存趋势数据（namespace={namespace}, pod={pod_name}）。"

        parsed = _parse_range_query_result(result)

        lines = [
            f"📈 内存使用趋势报告",
            f"{'='*50}",
            f"  命名空间: {namespace}" + (f", Pod: {pod_name}" if pod_name else ""),
            f"  时间范围: 最近 {duration_minutes} 分钟",
            f"{'='*50}",
        ]

        for p in parsed:
            pod = p["labels"].get("pod", "unknown")
            vals = [v for _, v in p["values"]]
            if not vals:
                continue
            avg_val = sum(vals) / len(vals)
            max_val = max(vals)
            min_val = min(vals)
            latest = vals[-1]

            lines.append(f"\n  📦 {pod}")
            lines.append(f"     最新: {_format_bytes_to_mib(latest)}")
            lines.append(f"     平均: {_format_bytes_to_mib(avg_val)}")
            lines.append(f"     最高: {_format_bytes_to_mib(max_val)}")
            lines.append(f"     最低: {_format_bytes_to_mib(min_val)}")

            # 趋势判断
            if len(vals) >= 5:
                first_half = sum(vals[:len(vals)//2]) / max(len(vals)//2, 1)
                second_half = sum(vals[len(vals)//2:]) / max(len(vals) - len(vals)//2, 1)
                change = (second_half - first_half) / max(first_half, 0.0001) * 100
                if change > 10:
                    lines.append(f"     📈 趋势: 增长中（+{change:.1f}%），可能存在内存泄漏风险")
                elif change < -10:
                    lines.append(f"     📉 趋势: 下降中（{change:.1f}%）")
                else:
                    lines.append(f"     ➡️ 趋势: 平稳（{change:+.1f}%）")

        if save_chart:
            try:
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
                import matplotlib.dates as mdates
                import numpy as np

                chart_dir = "./output/charts"
                os.makedirs(chart_dir, exist_ok=True)

                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                pod_label = pod_name if pod_name else "all"
                chart_path = os.path.join(chart_dir, f"mem_trend_{namespace}_{pod_label}_{timestamp}.png")

                fig, ax = plt.subplots(figsize=(12, 6))
                colors = plt.cm.tab10(np.linspace(0, 1, len(parsed)))

                for idx, p in enumerate(parsed):
                    pod = p["labels"].get("pod", "unknown")
                    if not p["values"]:
                        continue
                    times = [datetime.datetime.fromtimestamp(ts) for ts, _ in p["values"]]
                    vals_mib = [v / (1024 * 1024) for _, v in p["values"]]
                    ax.plot(times, vals_mib, marker='o', linestyle='-', linewidth=1.5,
                           markersize=3, label=pod, color=colors[idx % len(colors)])

                ax.set_xlabel('时间', fontsize=12)
                ax.set_ylabel('内存使用 (MiB)', fontsize=12)
                ax.set_title(f'内存使用趋势 — {namespace}' + (f' / {pod_name}' if pod_name else ''), fontsize=14)
                ax.legend(loc='best', fontsize=10)
                ax.grid(True, alpha=0.3)
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

                plt.tight_layout()
                plt.savefig(chart_path, dpi=150)
                plt.close()

                lines.append(f"\n📊 内存趋势图已保存至: {chart_path}")
            except Exception as chart_err:
                lines.append(f"\n⚠️ 图表生成失败: {str(chart_err)}")

        return "\n".join(lines)

    except ImportError:
        return "错误: 未安装 prometheus-api-client 库。"
    except Exception as e:
        return f"内存趋势查询失败: {str(e)}" + DIAGNOSIS_SUGGESTION


# ============================================================
# 工具 8: Pod 网络 I/O 查询
# ============================================================

@tool("query_pod_network_io")
def query_pod_network_io(
    namespace: str = "default",
    pod_name: str = "",
    prometheus_url: str = "http://localhost:9090"
) -> str:
    """
    【网络 I/O】查询 Pod 的网络接收/发送速率。
    典型提问："查看 bookinfo 各服务的网络流量"、"productpage 的网络 I/O"

    Args:
        namespace: Kubernetes 命名空间。
        pod_name: 可选，特定 Pod 名称前缀。
        prometheus_url: Prometheus 服务地址。
    """
    try:
        prom = _get_prometheus_client(prometheus_url)

        # 接收速率
        if pod_name:
            rx_promql = f'sum(rate(container_network_receive_bytes_total{{namespace="{namespace}",pod=~".*{pod_name}.*"}}[5m])) by (pod)'
            tx_promql = f'sum(rate(container_network_transmit_bytes_total{{namespace="{namespace}",pod=~".*{pod_name}.*"}}[5m])) by (pod)'
        else:
            rx_promql = f'sum(rate(container_network_receive_bytes_total{{namespace="{namespace}"}}[5m])) by (pod)'
            tx_promql = f'sum(rate(container_network_transmit_bytes_total{{namespace="{namespace}"}}[5m])) by (pod)'

        rx_result = prom.custom_query(query=rx_promql)
        tx_result = prom.custom_query(query=tx_promql)

        rx_parsed = {p["labels"].get("pod", ""): p["value"] for p in _parse_instant_query_result(rx_result)}
        tx_parsed = {p["labels"].get("pod", ""): p["value"] for p in _parse_instant_query_result(tx_result)}

        all_pods = set(list(rx_parsed.keys()) + list(tx_parsed.keys()))

        if not all_pods:
            return f"在命名空间 '{namespace}' 中未找到网络 I/O 数据。"

        lines = [
            f"🌐 网络 I/O 报告 — 命名空间: {namespace}",
            f"{'='*55}",
            f"{'Pod':<30} {'接收 (Rx)':<15} {'发送 (Tx)':<15}",
            f"{'-'*55}"
        ]

        for pod in sorted(all_pods):
            rx_bps = rx_parsed.get(pod, 0)
            tx_bps = tx_parsed.get(pod, 0)
            rx_str = f"{rx_bps:.1f} B/s" if rx_bps < 1024 else f"{rx_bps/1024:.1f} KB/s"
            tx_str = f"{tx_bps:.1f} B/s" if tx_bps < 1024 else f"{tx_bps/1024:.1f} KB/s"
            lines.append(f"{pod:<30} {rx_str:<15} {tx_str:<15}")

        lines.append(f"{'='*55}")
        return "\n".join(lines)

    except ImportError:
        return "错误: 未安装 prometheus-api-client 库。"
    except Exception as e:
        return f"网络 I/O 查询失败: {str(e)}" + DIAGNOSIS_SUGGESTION


# ============================================================
# 工具 9: Prometheus 健康检查
# ============================================================

@tool("prometheus_health_check")
def prometheus_health_check(
    prometheus_url: str = "http://localhost:9090"
) -> str:
    """
    【健康检查】检查 Prometheus 服务是否正常运行，返回 Prometheus 版本和运行状态。
    典型提问："Prometheus 是否正常运行"、"检查监控系统状态"

    Args:
        prometheus_url: Prometheus 服务地址。
    """
    import urllib.request

    try:
        # 检查 /-/ready 端点
        req = urllib.request.Request(f"{prometheus_url}/-/ready")
        with urllib.request.urlopen(req, timeout=5) as resp:
            ready = resp.status == 200

        # 获取版本信息
        req2 = urllib.request.Request(f"{prometheus_url}/api/v1/status/buildinfo")
        with urllib.request.urlopen(req2, timeout=5) as resp:
            build_info = json.loads(resp.read().decode())

        version = build_info.get("data", {}).get("version", "unknown")

        # 尝试获取 Targets 信息（可能因版本不同而不支持）
        targets_info = ""
        try:
            prom = _get_prometheus_client(prometheus_url)
            # 通过 Prometheus API 获取目标状态
            import urllib.request
            targets_url = f"{prometheus_url}/api/v1/targets"
            with urllib.request.urlopen(targets_url, timeout=5) as resp:
                targets_data = json.loads(resp.read().decode())
            targets = targets_data.get("data", {}).get("activeTargets", [])
            up_count = sum(1 for t in targets if t.get("health") == "up")
            total_count = len(targets)
            targets_info = f"\n  活跃 Targets: {up_count}/{total_count}"
        except Exception:
            targets_info = "\n  活跃 Targets: (无法获取)"

        return (
            f"✅ Prometheus 健康检查通过\n"
            f"{'='*40}\n"
            f"  状态: {'Running' if ready else 'Unhealthy'}\n"
            f"  版本: {version}\n"
            f"  地址: {prometheus_url}{targets_info}\n"
            f"{'='*40}\n"
            f"💡 Prometheus 运行正常，可执行监控查询。"
        )

    except Exception as e:
        return f"❌ Prometheus 健康检查失败: {str(e)}\n请确认 Prometheus 服务是否已启动并可访问。"


# ============================================================
# 工具 10: Jaeger 调用链查询
# ============================================================

@tool("jaeger_query_tool")
def jaeger_query_tool(
    service_name: str = "",
    limit: int = 10,
    jaeger_url: str = "http://localhost:16686"
) -> str:
    """
    【调用链】查询 Jaeger 分布式追踪系统的调用链数据。
    可用于分析服务间调用的耗时和错误。
    典型提问："查看 productpage 服务的调用链"、"Jaeger 中有哪些服务"

    Args:
        service_name: 服务名称，为空时列出所有已注册的服务。
        limit: 最大返回追踪数量（默认: 10）。
        jaeger_url: Jaeger 查询服务地址（默认: http://localhost:16686）。
    """
    import urllib.request

    try:
        if service_name:
            url = f"{jaeger_url}/api/traces?service={service_name}&limit={limit}"
        else:
            url = f"{jaeger_url}/api/services"

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        if service_name:
            traces = data.get("data", [])
            if not traces:
                return f"未找到服务 '{service_name}' 的追踪数据。"

            output = [
                f"🔗 Jaeger 调用链 — 服务: {service_name}",
                f"{'='*50}",
                f"返回追踪数: {len(traces)}",
                ""
            ]
            for i, trace in enumerate(traces[:limit]):
                spans = trace.get("spans", [])
                duration = 0
                for span in spans:
                    if span.get("startTime", 0) > 0:
                        span_duration = (span.get("duration", 0)) / 1000
                        duration = max(duration, span_duration)

                output.append(f"  Trace #{i+1}")
                output.append(f"    Span 数量: {len(spans)}")
                output.append(f"    最大耗时: {duration:.2f} ms")
                output.append("")
            return "\n".join(output)
        else:
            services = data.get("data", [])
            return (
                f"🔗 Jaeger 已注册的服务:\n"
                f"{'='*40}\n" +
                "\n".join(f"  - {s}" for s in services)
            )

    except Exception as e:
        return f"Jaeger 查询失败: {str(e)}" + DIAGNOSIS_SUGGESTION
