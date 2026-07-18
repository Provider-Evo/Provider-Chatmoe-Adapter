"""util 模块 — Provider 适配器层。

职责：
    提供运行期无关的小工具（路径解析、字符串转换、header 构造等）。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from typing import Any

from .core.constants import CAPS, MODELS

__all__ = [
    "Adapter",
    "ChatmoeAdapter",
    "MODELS",
    "CAPS",
]


def __getattr__(name: str) -> Any:
    """懒加载 Adapter / ChatmoeAdapter，避免顶层 import 触发 core 全量加载。"""
    if name in {"Adapter", "ChatmoeAdapter"}:
        from .core.adaptercore import Adapter as _Adapter  # noqa: PLC0415

        return _Adapter
    raise AttributeError(
        "module 'src.platforms.chatmoe.util' has no attribute {!r}".format(name)
    )
