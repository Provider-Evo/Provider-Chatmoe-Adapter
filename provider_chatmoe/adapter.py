"""adapter 模块 — Provider 适配器层。

职责：
    作为 SDK 兼容入口，转发到 provider_*.core 下的真实实现层。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from .util import Adapter, ChatmoeAdapter

__all__ = ["Adapter", "ChatmoeAdapter"]
