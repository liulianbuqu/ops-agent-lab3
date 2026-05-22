"""
日志工具模块
提供统一的日志记录功能，支持输出到文件和控制台
"""
import os
import logging
from datetime import datetime


def get_logger(save_dir: str = "./output/logs", task_name: str = "ops_agent"):
    """
    创建一个配置好的日志记录器。
    
    Args:
        save_dir: 日志文件保存目录
        task_name: 任务名称，用于日志文件名

    Returns:
        logging.Logger: 配置好的日志记录器实例
    """
    # 确保日志目录存在
    os.makedirs(save_dir, exist_ok=True)

    # 生成日志文件名：task_name_YYYYMMDD_HHMMSS.log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(save_dir, f"{task_name}_{timestamp}.log")

    # 创建日志记录器
    logger = logging.getLogger(task_name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 文件处理器 - 记录所有级别日志
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)

    # 控制台处理器 - 只记录 INFO 及以上级别
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(message)s"
    )
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
