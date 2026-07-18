"""constants 模块 — Provider 适配器层。

职责：
    集中放置 provider 常量定义（模型名、URL 模板、错误码等）。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from __future__ import annotations

BASE_URL = "https://chatmoe.cn"
CHAT_PATH = "/api/chat"
ABORT_PATH = "/api/chat/abort"
RESUME_PATH = "/api/chat/resume"

# 硬编码模型列表
MODELS: list[str] = [
    "flash-lite",
    "glm-4.5-flash",
]

# 能力字典
CAPS: dict[str, bool] = {
    "chat": True,
    "completions": True,
    "responses": True,
    "thinking": True,
    "search": True,
}

# 默认上下文长度
CONTEXT_LENGTH: int = 131072

# 是否允许用远程模型列表覆盖本地
FETCH_MODELS_ENABLED: bool = False

# 远程模型刷新间隔（秒）
MODEL_FETCH_INTERVAL: int = 86400

# Key 重新生成间隔（秒），类似 qwen 的定时登录
KEY_REFRESH_INTERVAL: int = 86400
