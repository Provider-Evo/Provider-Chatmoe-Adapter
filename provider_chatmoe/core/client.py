from __future__ import annotations

import asyncio
import uuid as _uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.dispatch.cand import Candidate, make_id
from src.foundation.config.reader import load_plugin_api_keys
from src.foundation.logger import get_logger
from .helpers.client_helpers import (
    abort_stream_request,
    parse_sse_stream,
    resume_stream_request,
)
from .consts import (
    BASE_URL, CHAT_PATH, CONTEXT_LENGTH, KEY_REFRESH_INTERVAL,
)
from .headers import build_headers
from .payload import build_payload

_PLUGIN_DIR = Path(__file__).resolve().parents[2]

logger = get_logger(__name__)
MAX_RETRIES: int = 3


class ChatmoeClient:
    """ChatMoe HTTP 客户端。

    特性：
    - 单候选项（UUID Key）
    - 流式 SSE 含 event/id/data 行解析
    - 支持 abort（停止生成）和 resume（继续生成）
    - 定时重新生成 Key（类似 qwen 定时登录）

    SSE 解析与 abort/resume 请求构造拆分至 ``client_helpers.py``。
    """

    def __init__(self) -> None:
        self._session: Any = None
        self._models: List[str] = []
        self._candidates: List[Candidate] = []
        # candidate.id -> stream_id（当前活跃流）
        self._active_streams: Dict[str, str] = {}
        # candidate.id -> last chunk id（用于 resume）
        self._stream_offsets: Dict[str, int] = {}
        self._key_refresh_task: Optional[asyncio.Task] = None

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化，不阻塞。"""
        self._session = session
        from ..accounts import API_KEYS

        self._api_keys = [k for k in API_KEYS if k and k.strip()]
        self._rebuild_candidates()
        logger.debug("chatmoe 客户端初始化完成，候选项: %d 个", len(self._candidates))

    async def background_setup(self) -> None:
        """后台启动 Key 定时刷新任务。"""
        self._key_refresh_task = asyncio.create_task(self._key_refresh_loop())

    def update_models(self, models: List[str]) -> None:
        """更新模型列表。"""
        self._models = list(models)
        for cand in self._candidates:
            cand.models = list(models)

    def _rebuild_candidates(self) -> None:
        """根据当前凭证重建候选项列表。"""
        from .consts import CAPS  # noqa: PLC0415

        self._candidates = [
            Candidate(
                id=make_id("chatmoe", key[:12]),
                platform="chatmoe",
                resource_id=key[:12],
                models=list(self._models),
                context_length=CONTEXT_LENGTH,
                meta={"api_key": key},
                **CAPS,
            )
            for key in self._api_keys
            if key
        ]

    async def candidates(self) -> List[Candidate]:
        """返回当前候选项列表。"""
        return list(self._candidates)

    async def ensure_candidates(self, count: int) -> int:
        """返回可用候选项数量。"""
        return len(self._candidates)

    # =========================================================================
    # Key 定时刷新（类似 qwen 定时登录）
    # =========================================================================

    async def _key_refresh_loop(self) -> None:
        """定时生成新 UUID Key，替换候选项凭证。"""
        try:
            while True:
                await asyncio.sleep(KEY_REFRESH_INTERVAL)
                self._regenerate_key()
        except asyncio.CancelledError:
            pass

    def _regenerate_key(self) -> None:
        """生成新 UUID 并重建候选项。

        注意：此刷新仅更新内存中的 ``self._api_keys``，不再写回持久化存储。
        进程重启后动态生成的 Key 会丢失，届时重新从 accounts.py 中的初始
        Key 启动（这是撤销 AdapterStore 依赖后的预期行为变化）。
        """
        new_key = str(_uuid.uuid4())
        self._api_keys = [new_key]
        self._rebuild_candidates()
        logger.info("chatmoe Key 已重新生成: %s...", new_key[:8])

    # =========================================================================
    # 聊天补全
    # =========================================================================

    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行聊天补全，含指数退避重试。"""
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                async for chunk in self._do_request(
                    candidate, messages, model, stream,
                    thinking=thinking, search=search,
                ):
                    yield chunk
                return
            except Exception as e:
                last_exc = e
                logger.warning(
                    "chatmoe 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, e
                )
        if last_exc is not None:
            raise last_exc

    async def _consume_chat_response(
        self,
        resp: aiohttp.ClientResponse,
        candidate: Candidate,
        stream: bool,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """解析聊天响应体（流式或非流式）。"""
        if stream:
            async for chunk in parse_sse_stream(
                resp, candidate.id, self._stream_offsets
            ):
                yield chunk
        else:
            obj = await resp.json()
            content_val: str = obj["choices"][0]["message"]["content"]
            yield content_val
            if obj.get("usage"):
                yield {"usage": obj["usage"]}

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次 HTTP 请求。"""
        token: str = candidate.meta.get("api_key", "")
        headers = build_headers(token)
        payload = build_payload(
            messages, model, token,
            stream=stream,
            thinking=thinking,
            search=search,
        )
        url = "{}{}".format(BASE_URL, CHAT_PATH)

        async with self._session.post(
            url,
            json=payload,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=10, total=300),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise Exception(
                    "chatmoe HTTP {}: {}".format(resp.status, body)
                )

            # 捕获 X-Stream-Id 用于 abort/resume
            stream_id = resp.headers.get("X-Stream-Id", "")
            if stream_id:
                self._active_streams[candidate.id] = stream_id
                self._stream_offsets[candidate.id] = 0

            async for chunk in self._consume_chat_response(resp, candidate, stream):
                yield chunk

            # 流结束后清理活跃标记
            self._active_streams.pop(candidate.id, None)

    # =========================================================================
    # Abort / Resume
    # =========================================================================

    async def abort_stream(self, candidate: Candidate) -> bool:
        """停止当前活跃的流式生成。

        Args:
            candidate: 候选项。

        Returns:
            是否成功停止。
        """
        stream_id = self._active_streams.get(candidate.id)
        if not stream_id:
            return False

        token: str = candidate.meta.get("api_key", "")
        ok = await abort_stream_request(self._session, token, stream_id)
        if ok:
            self._active_streams.pop(candidate.id, None)
            self._stream_offsets.pop(candidate.id, None)
        return ok

    async def resume_stream(
        self,
        candidate: Candidate,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """从上次中断处继续生成。

        Args:
            candidate: 候选项。

        Yields:
            文本片段或结构化数据字典。
        """
        stream_id = self._active_streams.get(candidate.id)
        offset = self._stream_offsets.get(candidate.id, 0)
        if not stream_id:
            return

        token: str = candidate.meta.get("api_key", "")

        try:
            resp_cm = await resume_stream_request(
                self._session, token, stream_id, offset
            )
            async with resp_cm as resp:
                if resp.status != 200:
                    logger.warning("chatmoe resume HTTP %d", resp.status)
                    return

                # resume 可能返回新的 stream_id
                new_sid = resp.headers.get("X-Stream-Id", stream_id)
                self._active_streams[candidate.id] = new_sid

                async for chunk in parse_sse_stream(
                    resp, candidate.id, self._stream_offsets
                ):
                    yield chunk
        except Exception as e:
            logger.warning("chatmoe resume 失败: %s", e)

    async def close(self) -> None:
        """清理资源。"""
        if self._key_refresh_task and not self._key_refresh_task.done():
            self._key_refresh_task.cancel()
            try:
                await self._key_refresh_task
            except asyncio.CancelledError:
                pass
