import asyncio
from collections.abc import Coroutine
from typing import Any

from app.core.database import db_manager


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Helper for running asynchronous domain logic inside Celery worker tasks.
    Ensures MongoDB connection pool is properly initialized on the task's event loop.
    Supports execution both from plain threads and from active async loops (such as pytest).
    """

    async def _runner():
        need_close = False
        if db_manager.client is None:
            await db_manager.connect()
            need_close = True
        try:
            return await coro
        finally:
            if need_close:
                await db_manager.disconnect()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, _runner()).result()
    else:
        return asyncio.run(_runner())
