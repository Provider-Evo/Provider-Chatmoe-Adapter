


from typing import Any

from .core.consts import CAPS, MODELS

__all__ = [
    "Adapter",
    "ChatmoeAdapter",
    "MODELS",
    "CAPS",
]


def __getattr__(name: str) -> Any:
    """懒加载 Adapter / ChatmoeAdapter，避免顶层 import 触发 core 全量加载。"""
    if name in {"Adapter", "ChatmoeAdapter"}:
        from .core.acore import Adapter as _Adapter  # noqa: PLC0415

        return _Adapter
    raise AttributeError(
        "module 'src.platforms.chatmoe.util' has no attribute {!r}".format(name)
    )
