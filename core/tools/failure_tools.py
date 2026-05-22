"""
故障诊断工具
当智能体在执行任务过程中遇到错误时，调用此工具进行根因分析和修复建议
"""
from langchain_core.tools import tool

from core.helper.llm_util import init_llm

FAILURE_DIAGNOSIS_PROMPT_TEMPLATE = """
You are an expert DevOps engineer with deep knowledge of Docker, Kubernetes, and cloud-native technologies.

## Failure Details
{failure_msg}

## Task
Please analyze the root cause of the above failure and provide a clear solution strategy.

## Response Requirements
1. Identify the MOST LIKELY root cause (be specific, not generic).
2. Suggest a concrete fix or next step to resolve the issue.
3. Keep your response under 150 words.
4. Output in a single paragraph.
5. Do NOT ask for user confirmation — just provide the diagnosis and fix.
6. Only include helpful technical information.
"""


@tool("failure_diagnosis_tool")
def failure_diagnosis_tool(failure_msg: str) -> str:
    """
    Analyze a failure message, identify the root cause, and suggest a solution.

    Use this tool when any other tool returns an error or unexpected result.
    The LLM will analyze the error and provide debugging guidance.

    Args:
        failure_msg: The error message, log output, or description of the current failure.
    """
    try:
        llm = init_llm()

        prompt = FAILURE_DIAGNOSIS_PROMPT_TEMPLATE.format(failure_msg=failure_msg)

        response = llm.invoke(prompt)

        diagnosis = response.content.strip()

        return (
            f"🔍 故障诊断结果:\n"
            f"{'='*40}\n"
            f"{diagnosis}\n"
            f"{'='*40}\n"
            f"💡 建议: 根据诊断结果调整后，请重新尝试之前的操作步骤。"
        )
    except Exception as e:
        return (
            f"故障诊断工具本身出现异常: {str(e)}\n"
            f"请手动检查错误信息并排查问题。\n"
            f"原始错误:\n{failure_msg}"
        )
