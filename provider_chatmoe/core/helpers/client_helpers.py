from __future__ import annotations

"""ChatMoe HTTP 客户端辅助模块。

职责：
    承载 SSE event/data/id 行解析与 abort/resume 请求逻辑，供
    ``client.py`` 中的 :class:`ChatmoeClient` facade 调用。拆分自
    ``client.py``，不改变任何现有行为。
"""

from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

import aiohttp

from src.foundation.logger import get_logger
from ..constants import ABORT_PATH, BASE_URL, RESUME_PATH
from ..headers import build_headers
from .sse import parse_sse_line

logger = get_logger(__name__)


def parse_event_block(event_block: str) -> Tuple[int, str]:
    """解析单个 SSE event block，返回 (chunk_id, data_str)。

    Args:
        event_block: 以空行分隔的单个事件块文本。

    Returns:
        (chunk_id, data_str) 二元组；无 data 行时 data_str 为空串。
    """
    lines = event_block.split("\n")
    chunk_id = 0
    data_parts = []
    for line in lines:
        if line.startswith("id:"):
            try:
                chunk_id = int(line[3:].strip())
            except ValueError:
                pass
        elif line.startswith("data:"):
            data_parts.append(line[5:].strip())
    return chunk_id, "\n".join(data_parts).strip()


def handle_sse_delta(
    delta: Dict[str, Any],
    thinking_started: bool,
    thinking_ended: bool,
) -> Tuple[List[Union[str, Dict[str, Any]]], bool, bool]:
    """处理单条 delta 中的 reasoning_content/content，产出对应片段。

    Returns:
        (items, thinking_started, thinking_ended) 三元组，items 为待
        yield 的片段列表。
    """
    items: List[Union[str, Dict[str, Any]]] = []
    reasoning_content: Optional[str] = delta.get("reasoning_content")
    content: Optional[str] = delta.get("content")

    if reasoning_content:
        if not thinking_started:
            items.append({"thinking": "<think>"})
            thinking_started = True
        items.append({"thinking": reasoning_content})

    if content:
        if thinking_started and not thinking_ended:
            items.append({"thinking": "</think>\n\n"})
            thinking_ended = True
        items.append(content)

    return items, thinking_started, thinking_ended


def _handle_choice_delta(
    data: Dict[str, Any],
    choices: List[Dict[str, Any]],
    thinking_started: bool,
    thinking_ended: bool,
) -> Tuple[List[Union[str, Dict[str, Any]]], bool, bool, bool]:
    """处理存在 choices 时的单条事件，产出对应片段。"""
    delta = choices[0].get("delta", {})
    items, thinking_started, thinking_ended = handle_sse_delta(
        delta, thinking_started, thinking_ended,
    )

    if choices[0].get("finish_reason"):
        if thinking_started and not thinking_ended:
            items.append({"thinking": "</think>\n\n"})
        return items, thinking_started, thinking_ended, True

    if data.get("usage"):
        items.append({"usage": data["usage"]})
    return items, thinking_started, thinking_ended, False


async def handle_event_block(
    event_block: str,
    candidate_id: str,
    stream_offsets: Dict[str, int],
    thinking_started: bool,
    thinking_ended: bool,
) -> Tuple[List[Union[str, Dict[str, Any]]], bool, bool, bool]:
    """处理单个 SSE event block，产出对应片段。

    Args:
        event_block: 单个事件块文本。
        candidate_id: 候选项 id，用于更新 stream_offsets。
        stream_offsets: candidate.id -> last chunk id 映射，就地更新。
        thinking_started: 是否已输出 <think> 起始标记。
        thinking_ended: 是否已输出 </think> 结束标记。

    Returns:
        (items, thinking_started, thinking_ended, finished) 四元组；
        finished 为 True 时调用方应停止整个流的解析。
    """
    chunk_id, data_str = parse_event_block(event_block)
    if data_str == "[DONE]":
        return [], thinking_started, thinking_ended, True
    if not data_str:
        return [], thinking_started, thinking_ended, False

    if chunk_id > 0:
        stream_offsets[candidate_id] = chunk_id

    data = parse_sse_line(data_str)
    if data is None or not isinstance(data, dict):
        return [], thinking_started, thinking_ended, False

    choices = data.get("choices", [])
    if not choices:
        items = [{"usage": data["usage"]}] if data.get("usage") else []
        return items, thinking_started, thinking_ended, False

    return _handle_choice_delta(data, choices, thinking_started, thinking_ended)


async def parse_sse_stream(
    resp: Any,
    candidate_id: str,
    stream_offsets: Dict[str, int],
) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
    """解析 SSE 流，处理 event/data/id 行。

    Args:
        resp: HTTP 响应对象。
        candidate_id: 候选项 id。
        stream_offsets: candidate.id -> last chunk id 映射，就地更新。

    Yields:
        文本片段或结构化数据字典。
    """
    buffer = ""
    thinking_started = False
    thinking_ended = False

    async for raw in resp.content:
        if not raw:
            continue
        buffer += raw.decode("utf-8", errors="replace")

        while "\n\n" in buffer:
            event_block, buffer = buffer.split("\n\n", 1)
            items, thinking_started, thinking_ended, finished = (
                await handle_event_block(
                    event_block, candidate_id, stream_offsets,
                    thinking_started, thinking_ended,
                )
            )
            for item in items:
                yield item
            if finished:
                return


async def abort_stream_request(
    session: aiohttp.ClientSession,
    token: str,
    stream_id: str,
) -> bool:
    """发起 abort 请求，停止当前活跃的流式生成。

    Args:
        session: 共享的 aiohttp ClientSession。
        token: API Key/Token。
        stream_id: 目标流 id。

    Returns:
        是否成功停止。
    """
    headers = build_headers(token)
    url = "{}{}".format(BASE_URL, ABORT_PATH)

    try:
        async with session.post(
            url,
            json={"streamId": stream_id},
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=5, total=15),
        ) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        logger.warning("chatmoe abort 失败: %s", e)
        return False


async def resume_stream_request(
    session: aiohttp.ClientSession,
    token: str,
    stream_id: str,
    offset: int,
) -> Any:
    """发起 resume 请求，从上次中断处继续生成。

    Args:
        session: 共享的 aiohttp ClientSession。
        token: API Key/Token。
        stream_id: 目标流 id。
        offset: 上次中断处的 chunk 偏移量。

    Returns:
        成功时返回 (resp, new_stream_id) 二元组；失败时返回 None。
        调用方负责在 ``async with`` 块外维持 resp 的生命周期，因此本
        函数直接返回底层 context manager 供调用方自行进入。
    """
    headers = build_headers(token)
    url = "{}{}".format(BASE_URL, RESUME_PATH)
    return session.post(
        url,
        json={"streamId": stream_id, "offset": offset},
        headers=headers,
        ssl=False,
        timeout=aiohttp.ClientTimeout(connect=10, total=300),
    )
