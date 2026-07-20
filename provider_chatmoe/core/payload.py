


from typing import Any, Dict, List


def build_payload(
    messages: List[Dict[str, Any]],
    model: str,
    token: str,
    *,
    stream: bool = True,
    thinking: bool = False,
    search: bool = False,
) -> Dict[str, Any]:
    """构建聊天请求体。

    Args:
        messages: 消息列表。
        model: 模型名称。
        token: UUID Key，同时作为 user_id。
        stream: 是否流式输出。
        thinking: 是否启用深度思考。
        search: 是否启用联网搜索。

    Returns:
        请求体字典。
    """
    return {
        "model": model,
        "stream": stream,
        "user_id": token,
        "tools": [
            {
                "type": "web_search",
                "web_search": {
                    "search_engine": "search_std",
                    "enable": search,
                },
            }
        ],
        "thinking": {"type": "enabled" if thinking else "disabled"},
        "messages": [
            {
                "role": m.get("role", "user"),
                "content": m.get("content", ""),
            }
            for m in messages
        ],
        "type": "text",
    }

__all__: List[str] = []
