"""sse 模块 — Provider 适配器层。

职责：
    提供流式响应的 Server-Sent Events 解析与重组工具。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



import json
from typing import Any, Dict, Optional, Union


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析单条 SSE data 字符串，返回 yield 值或 None。

    无状态版本，仅解析 JSON 并提取字段。

    Args:
        data_str: SSE data 字段内容（去除 "data:" 前缀）。

    Returns:
        解析后的 yield 值，解析失败或无内容返回 None。
    """
    try:
        return json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None

__all__ = [
    "parse_sse_line",
]
