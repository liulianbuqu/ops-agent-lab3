"""
Kubernetes 相关工具
包括 K8s YAML 生成、资源部署、状态检查、日志获取等
"""
import os
import subprocess
import json
import tempfile
from langchain_core.tools import tool

from core.helper.llm_util import init_llm
from core.tools.file_tools import read_file_content, write_file_content

DIAGNOSIS_SUGGESTION = (
    "\n\n[提示] 如果上述输出包含错误信息，"
    "建议调用 failure_diagnosis_tool 进行故障分析。"
)

# ========== K8s YAML 生成工具 ==========

K8S_YAML_PROMPT_TEMPLATE = """
You are a Kubernetes expert. Generate Kubernetes YAML configuration files based on the following requirements.

## Service Info
- Service Name: {service_name}
- Container Image: {image}
- Container Port: {container_port}
- Replicas: {replicas}
- Namespace: {namespace}
- Service Type: {service_type}

## Requirements
Generate TWO YAML resources separated by `---`:
1. A **Deployment** with the specified name, image, port, replicas, and namespace.
2. A **Service** of the specified type that exposes the deployment's port.

## Guidelines
- Use apiVersion apps/v1 for Deployment and v1 for Service.
- Add proper labels and selector matches.
- Include resource requests and limits (CPU: 200m/500m, Memory: 256Mi/512Mi).
- Set the namespace correctly.
- For Service type, use "ClusterIP" for internal access or "NodePort"/"LoadBalancer" for external access.

## Output Format
Output ONLY the YAML content wrapped in ```yaml blocks, no explanation.
"""


@tool("k8s_yaml_generate_tool")
def k8s_yaml_generate_tool(
    service_name: str,
    image: str,
    container_port: int = 8080,
    replicas: int = 1,
    namespace: str = "default",
    service_type: str = "ClusterIP",
    save_path: str = ""
) -> str:
    """
    Generate Kubernetes Deployment and Service YAML files using LLM.

    Args:
        service_name: Name of the service and deployment.
        image: Container image tag (e.g., 'my-app:latest').
        container_port: Port that the container listens on.
        replicas: Number of pod replicas.
        namespace: Kubernetes namespace.
        service_type: Service type - ClusterIP, NodePort, or LoadBalancer.
        save_path: Path to save the generated YAML file. If empty, generates a default path.
    """
    if not save_path:
        save_path = f"./output/k8s/{service_name}-deployment.yaml"

    prompt = K8S_YAML_PROMPT_TEMPLATE.format(
        service_name=service_name,
        image=image,
        container_port=container_port,
        replicas=replicas,
        namespace=namespace,
        service_type=service_type
    )

    try:
        llm = init_llm()
        response = llm.invoke(prompt)
        yaml_text = response.content.strip()

        # 清理 markdown 代码块标记
        yaml_text = yaml_text.replace("```yaml", "").replace("```", "").strip()

        result = write_file_content(yaml_text, save_path)
        return f"{result}\n\n生成的 YAML 文件: {save_path}\n\n{yaml_text}"
    except Exception as e:
        return f"K8s YAML 生成失败: {str(e)}" + DIAGNOSIS_SUGGESTION


# ========== K8s 资源部署工具 ==========

@tool("k8s_apply_tool")
def k8s_apply_tool(yaml_file_path: str) -> str:
    """
    Apply a Kubernetes YAML configuration file to the cluster using kubectl apply.

    Args:
        yaml_file_path: Path to the YAML file to apply.
    """
    cmd = ["kubectl", "apply", "-f", yaml_file_path]

    full_log = []
    try:
        # 先检查 kubectl 是否可用
        subprocess.run(
            ["kubectl", "version", "--client"],
            capture_output=True,
            check=True
        )

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        for line in proc.stdout:
            full_log.append(line)
            print(line, end="")

        proc.stdout.close()
        proc.wait()

        if proc.returncode == 0:
            full_log.append("\n资源部署成功！")
        else:
            full_log.append(f"\n部署失败，返回码: {proc.returncode}")

    except FileNotFoundError:
        return "错误: 未找到 kubectl 命令，请确保 kubectl 已安装并添加到 PATH。"
    except subprocess.CalledProcessError:
        return "错误: kubectl 不可用，请确保已安装并配置 Kubernetes 集群。"
    except Exception as e:
        full_log.append(f"异常: {str(e)}\n")

    return "".join(full_log) + DIAGNOSIS_SUGGESTION


# ========== Pod 状态检查工具 ==========

@tool("k8s_pod_status_tool")
def k8s_pod_status_tool(namespace: str = "default", label_selector: str = "") -> str:
    """
    Check the status of Pods in a Kubernetes namespace.

    Args:
        namespace: The Kubernetes namespace to query.
        label_selector: Optional label selector to filter pods (e.g., 'app=my-service').
    """
    cmd = [
        "kubectl", "get", "pods",
        "-n", namespace,
        "-o", "wide"
    ]
    if label_selector:
        cmd.extend(["-l", label_selector])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        output = result.stdout

        # 统计 Pod 状态
        lines = output.strip().split("\n")
        if len(lines) <= 1:
            return f"命名空间 '{namespace}' 中没有找到 Pod。\n{output}"

        running_count = sum(1 for line in lines[1:] if "Running" in line)
        pending_count = sum(1 for line in lines[1:] if "Pending" in line)
        failed_count = sum(1 for line in lines[1:] if "Error" in line or "CrashLoopBackOff" in line or "ImagePullBackOff" in line)
        total = len(lines) - 1

        summary = (
            f"命名空间: {namespace}\n"
            f"Pod 总数: {total}\n"
            f"  Running: {running_count}\n"
            f"  Pending: {pending_count}\n"
            f"  异常状态: {failed_count}\n\n"
        )

        if failed_count > 0:
            summary += "⚠️ 存在异常 Pod，建议进一步检查。\n\n"

        return summary + output

    except FileNotFoundError:
        return "错误: 未找到 kubectl 命令。"
    except subprocess.CalledProcessError as e:
        return f"查询 Pod 状态失败:\n{e.stderr}" + DIAGNOSIS_SUGGESTION
    except Exception as e:
        return f"异常: {str(e)}" + DIAGNOSIS_SUGGESTION


# ========== K8s 资源删除工具 ==========

@tool("k8s_delete_tool")
def k8s_delete_tool(yaml_file_path: str = "", resource_type: str = "", resource_name: str = "", namespace: str = "default") -> str:
    """
    Delete Kubernetes resources by YAML file or by specifying resource type and name.

    Args:
        yaml_file_path: Path to the YAML file defining resources to delete (optional).
        resource_type: Resource type to delete (e.g., 'deployment', 'service'). Used with resource_name.
        resource_name: Name of the resource to delete. Used with resource_type.
        namespace: Namespace of the resource (default: 'default').
    """
    try:
        if yaml_file_path:
            cmd = ["kubectl", "delete", "-f", yaml_file_path]
        elif resource_type and resource_name:
            cmd = ["kubectl", "delete", resource_type, resource_name, "-n", namespace]
        else:
            return "错误: 请提供 YAML 文件路径或资源类型+名称。"

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return f"资源删除成功:\n{result.stdout}"
        else:
            return f"资源删除失败:\n{result.stderr}" + DIAGNOSIS_SUGGESTION

    except FileNotFoundError:
        return "错误: 未找到 kubectl 命令。"
    except Exception as e:
        return f"异常: {str(e)}"


# ========== 命名空间管理工具 ==========

@tool("k8s_namespace_tool")
def k8s_namespace_tool(namespace: str, action: str = "create") -> str:
    """
    Create or check if a Kubernetes namespace exists.

    Args:
        namespace: The namespace name.
        action: 'create' to create if not exists, 'check' to only check existence.
    """
    try:
        # 检查命名空间是否存在
        check = subprocess.run(
            ["kubectl", "get", "namespace", namespace],
            capture_output=True, text=True
        )

        if check.returncode == 0:
            return f"命名空间 '{namespace}' 已存在。"

        if action == "create":
            result = subprocess.run(
                ["kubectl", "create", "namespace", namespace],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return f"命名空间 '{namespace}' 创建成功！"
            else:
                return f"创建命名空间失败:\n{result.stderr}" + DIAGNOSIS_SUGGESTION
        else:
            return f"命名空间 '{namespace}' 不存在。"

    except FileNotFoundError:
        return "错误: 未找到 kubectl 命令。"
    except Exception as e:
        return f"异常: {str(e)}"
