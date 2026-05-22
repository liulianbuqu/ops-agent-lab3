"""
LLM 初始化与配置模块
支持通过环境变量或硬编码方式配置 DeepSeek API
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 加载 .env 文件中的环境变量（如果有）
load_dotenv()


def init_llm():
    """
    初始化并返回一个配置好的 ChatOpenAI 实例。
    
    优先从环境变量读取 API Key 和 Base URL，
    如果未设置则使用硬编码的默认值（仅用于开发测试）。
    
    Returns:
        ChatOpenAI: 配置好的大模型实例
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    if not api_key:
        raise ValueError(
            "未检测到 DEEPSEEK_API_KEY 环境变量！\n"
            "请设置环境变量：\n"
            "  $env:DEEPSEEK_API_KEY = \"sk-你的API Key\"\n"
            "或在项目根目录创建 .env 文件：\n"
            "  DEEPSEEK_API_KEY=sk-你的API Key\n"
            "  DEEPSEEK_BASE_URL=https://api.deepseek.com/v1\n"
            "  DEEPSEEK_MODEL=deepseek-chat"
        )

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0,          # 运维场景需要低随机性，确保输出稳定
        max_retries=2,
        timeout=60,             # 60秒超时，防止长尾延迟
    )
    return llm
