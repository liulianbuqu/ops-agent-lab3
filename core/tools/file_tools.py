"""
文件读写工具
通过对 Python 文件读写接口的封装，提供给智能体调用
"""
from langchain_core.tools import tool


def read_file_content(file_path: str) -> str:
    """读取文件内容的辅助函数。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except FileNotFoundError:
        return f"错误：文件 {file_path} 不存在"
    except Exception as e:
        return f"读取文件失败: {str(e)}"


def write_file_content(content: str, file_path: str) -> str:
    """写入文件内容的辅助函数。"""
    try:
        import os
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"成功将内容写入文件: {file_path}"
    except Exception as e:
        return f"写入文件失败 {file_path}: {str(e)}"


@tool("file_read_tool")
def file_read_tool(file_path: str) -> str:
    """
    Read the contents of a file at the specified path.

    Args:
        file_path: The full path of the file to read.
    """
    return read_file_content(file_path)


@tool("file_write_tool")
def file_write_tool(content: str, file_path: str) -> str:
    """
    Write content into a file at the specified path.
    Creates intermediate directories if they don't exist.

    Args:
        content: The content to write into the file.
        file_path: The full path of the file to be written.
    """
    return write_file_content(content, file_path)


@tool("file_list_tool")
def file_list_tool(directory_path: str) -> str:
    """
    List all files and subdirectories in the specified directory.

    Args:
        directory_path: The path of the directory to list.
    """
    import os
    try:
        items = os.listdir(directory_path)
        result = []
        for item in items:
            full_path = os.path.join(directory_path, item)
            if os.path.isdir(full_path):
                result.append(f"[DIR]  {item}")
            else:
                size = os.path.getsize(full_path)
                result.append(f"[FILE] {item} ({size} bytes)")
        return "\n".join(result) if result else "目录为空"
    except Exception as e:
        return f"列出目录失败: {str(e)}"
