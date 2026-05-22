"""
Docker 相关工具
包括 Dockerfile 生成、镜像构建、容器运行、容器内命令执行
"""
import os
import subprocess
from langchain_core.tools import tool

from core.helper.llm_util import init_llm
from core.prompts.dockerfile_prompt import DOCKERFILE_PROMPT_TEMPLATE
from core.tools.file_tools import read_file_content, write_file_content

# 诊断提示语，引导智能体在出错时使用故障诊断工具
DIAGNOSIS_SUGGESTION = (
    "\n\n[提示] 如果上述输出包含错误信息，"
    "建议调用 failure_diagnosis_tool 进行故障分析。"
)


# ========== Dockerfile 生成工具 ==========

@tool("dockerfile_generate_tool")
def dockerfile_generate_tool(
    readme_path: str,
    project_path: str,
    save_path: str
) -> str:
    """
    Generate a Dockerfile based on a project's README.md using LLM, and save it.

    Args:
        readme_path: Path to the README.md file that describes the project requirements.
        project_path: Path of the project directory where the Dockerfile will be used.
        save_path: Path where the generated Dockerfile should be saved.
    """
    # 读取 README 内容
    requirement = read_file_content(readme_path)
    if requirement.startswith("错误"):
        return requirement

    # 调用 LLM 生成 Dockerfile
    prompt = DOCKERFILE_PROMPT_TEMPLATE.format(
        requirement=requirement,
        project_path=project_path
    )
    try:
        llm = init_llm()
        response = llm.invoke(prompt)
        dockerfile_text = response.content.strip()

        # 清理可能存在的 markdown 代码块标记
        dockerfile_text = dockerfile_text.replace("```dockerfile", "").replace("```", "").strip()

        # 写入文件
        result = write_file_content(dockerfile_text, save_path)
        return result + DIAGNOSIS_SUGGESTION
    except Exception as e:
        return f"Dockerfile 生成失败: {str(e)}" + DIAGNOSIS_SUGGESTION


# ========== Docker 镜像构建工具 ==========

@tool("image_build_tool")
def image_build_tool(docker_file_path: str, image_tag: str) -> str:
    """
    Build a Docker image from a specific Dockerfile.

    Args:
        docker_file_path: Full path to the Dockerfile.
        image_tag: Tag name for the resulting image (e.g., 'my-app:latest').
    """
    docker_dir = os.path.dirname(docker_file_path)
    dockerfile_name = os.path.basename(docker_file_path)

    cmd = [
        "docker", "build",
        "-t", image_tag,
        "-f", dockerfile_name,
        "."
    ]

    full_log = []
    original_dir = os.getcwd()

    try:
        os.chdir(docker_dir)

        # 先尝试移除已存在的同名镜像（忽略错误）
        try:
            subprocess.run(
                ["docker", "rmi", "-f", image_tag],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

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
            print(line, end="")  # 实时输出到控制台

        proc.stdout.close()
        proc.wait()

    except FileNotFoundError:
        full_log.append("错误: 未找到 docker 命令，请确保 Docker 已安装并添加到 PATH。\n")
    except Exception as e:
        full_log.append(f"异常: {str(e)}\n")
    finally:
        os.chdir(original_dir)

    return "".join(full_log) + DIAGNOSIS_SUGGESTION


# ========== 容器运行工具 ==========

@tool("container_run_tool")
def container_run_tool(
    image_tag: str,
    container_name: str,
    internal_port: int = 8080,
    expose_port: int = 8080
) -> str:
    """
    Start and run a Docker container from a specified image.

    Args:
        image_tag: The tag of the image to run the container from.
        container_name: The name to assign to the new container.
        internal_port: Port used inside the container.
        expose_port: The host port to map to the container's internal port.
    """
    # 先尝试停止并移除同名容器
    try:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

    cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "-p", f"{expose_port}:{internal_port}",
        image_tag
    ]

    full_log = []
    try:
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

        proc.stdout.close()
        proc.wait()

        if proc.returncode == 0:
            container_id = full_log[-1].strip() if full_log else "未知"
            full_log.append(f"\n容器 '{container_name}' 已成功启动！")
            full_log.append(f"访问地址: http://localhost:{expose_port}")
        else:
            full_log.append(f"\n容器启动失败，返回码: {proc.returncode}")

    except FileNotFoundError:
        full_log.append("错误: 未找到 docker 命令，请确保 Docker 已安装并添加到 PATH。\n")
    except Exception as e:
        full_log.append(f"异常: {str(e)}\n")

    return "".join(full_log) + DIAGNOSIS_SUGGESTION


# ========== 容器内命令执行工具 ==========

@tool("container_exec_cmd_tool")
def container_exec_cmd_tool(container_name: str, command: str) -> str:
    """
    Execute a shell command inside an already running Docker container.

    Args:
        container_name: The name of the target container.
        command: The shell command to execute inside the container.
    """
    import docker
    from docker.errors import NotFound

    client = docker.from_env()
    try:
        container = client.containers.get(container_name)

        exit_code, output = container.exec_run(
            cmd=command,
            stdout=True,
            stderr=True,
            demux=False,
            tty=False
        )

        output_text = output.decode(errors="ignore") if output else ""
        result = f"Exit code: {exit_code}\n\nOutput:\n{output_text}"

        if exit_code != 0:
            result += DIAGNOSIS_SUGGESTION

        return result

    except NotFound:
        return f"错误: 容器 '{container_name}' 未找到。" + DIAGNOSIS_SUGGESTION
    except Exception as e:
        return f"命令执行失败: {str(e)}" + DIAGNOSIS_SUGGESTION


# ========== 容器日志查看工具 ==========

@tool("container_logs_tool")
def container_logs_tool(container_name: str, tail: int = 100) -> str:
    """
    Fetch and return the logs of a running or stopped Docker container.

    Args:
        container_name: The name of the container.
        tail: Number of log lines to show from the end (default: 100).
    """
    import docker
    from docker.errors import NotFound

    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
        logs = container.logs(tail=tail, stdout=True, stderr=True)
        return logs.decode(errors="ignore")
    except NotFound:
        return f"错误: 容器 '{container_name}' 未找到。"
    except Exception as e:
        return f"获取日志失败: {str(e)}"
