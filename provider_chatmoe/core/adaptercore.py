"""ChatMoe 平台适配器实现。"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.dispatch.candidate import Candidate
from src.core.utils.compat.models_cache import ModelsCache
from src.foundation.logger import get_logger
from provider_sdk.extensions.platform.adapter import PlatformAdapter
from .client import ChatmoeClient
from .constants import (
    CAPS,
    FETCH_MODELS_ENABLED,
    MODEL_FETCH_INTERVAL,
    MODELS,
)

__all__ = ["Adapter", "ChatmoeAdapter"]

logger = get_logger(__name__)


class Adapter(PlatformAdapter):
    """ChatMoe 平台适配器。"""

    def __init__(self) -> None:
        self._client: Any = None
        self._models: List[str] = list(MODELS)
        self._cache: Optional[ModelsCache] = None
        self._refresh_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

    @property
    def name(self) -> str:
        """返回平台标识符。"""
        return "chatmoe"

    @property
    def supported_models(self) -> List[str]:
        """返回当前支持的模型列表。"""
        return list(self._models)

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """返回平台默认能力字典。"""
        return CAPS

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器——立即注册，后台完善。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._client = ChatmoeClient()
        # 立即初始化，不阻塞
        await self._client.init_immediate(session)
        # 加载模型缓存
        self._cache = ModelsCache(
            platform="chatmoe",
            fallback_models=MODELS,
            fetch_enabled=FETCH_MODELS_ENABLED,
        )
        cached = await self._cache.load()
        if cached:
            self._models = cached
            self._client.update_models(self._models)
        # 启动后台任务
        self._refresh_task = asyncio.ensure_future(self._background_init())

    async def _background_init(self) -> None:
        """后台初始化：完成耗时操作后持续刷新。"""
        try:
            await self._client.background_setup()
        except Exception as e:
            logger.warning("chatmoe 后台初始化失败: %s", e)
        # 启动模型定时刷新
        if self._cache is not None:
            asyncio.ensure_future(
                self._cache.start_refresh_loop(
                    fetch_fn=self.fetch_remote_models,
                    interval=MODEL_FETCH_INTERVAL,
                    on_update=self._on_models_updated,
                )
            )

    async def _on_models_updated(self, models: List[str]) -> None:
        """模型列表更新回调。

        Args:
            models: 更新后的模型列表。
        """
        self._models = models
        if self._client is not None:
            self._client.update_models(models)
        logger.debug("chatmoe 模型列表已更新: %d 个", len(models))

    async def fetch_remote_models(self) -> List[str]:
        """拉取远程模型列表。

        ChatMoe 无公开模型接口，返回本地硬编码列表。

        Returns:
            模型名称列表。
        """
        return list(MODELS)

    async def candidates(self) -> List[Candidate]:
        """返回当前可用候选项。

        Returns:
            候选项列表。
        """
        if self._client is None:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """确保候选项数量。

        Args:
            count: 期望的最少候选项数量。

        Returns:
            当前实际候选项数量。
        """
        if self._client is None:
            return 0
        return await self._client.ensure_candidates(count)

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
        """聊天补全，委托给 client。

        Args:
            candidate: 选中的候选项。
            messages: 消息列表。
            model: 模型名称。
            stream: 是否流式输出。
            thinking: 是否启用深度思考。
            search: 是否启用联网搜索。
            **kw: 其他扩展参数。

        Yields:
            文本片段或结构化数据字典。
        """
        async for chunk in self._client.complete(
            candidate,
            messages,
            model,
            stream,
            thinking=thinking,
            search=search,
            **kw,
        ):
            yield chunk

    async def abort_stream(self, candidate: Candidate) -> bool:
        """停止当前活跃的流式生成。

        Args:
            candidate: 候选项。

        Returns:
            是否成功停止。
        """
        if self._client is None:
            return False
        return await self._client.abort_stream(candidate)

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
        if self._client is None:
            return
        async for chunk in self._client.resume_stream(candidate):
            yield chunk

    async def close(self) -> None:
        """关闭适配器，释放资源。"""
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                logger.debug("chatmoe refresh task cancelled")
        if self._client is not None:
            await self._client.close()


ChatmoeAdapter = Adapter
