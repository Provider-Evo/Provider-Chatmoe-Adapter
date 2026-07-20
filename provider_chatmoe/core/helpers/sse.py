


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
