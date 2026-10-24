"""Cancellable background work that waits for resource cleanup before returning."""

import asyncio
from collections.abc import Callable
from typing import TypeVar

from .providers.base import CancellationToken

Result = TypeVar("Result")


async def run_blocking_work(
    operation: Callable[[CancellationToken], Result],
    cancellation_token: CancellationToken | None,
) -> Result:
    """Propagate cancellation to blocking work and await its controlled cleanup."""
    token = cancellation_token or CancellationToken()
    token.raise_if_cancelled()
    worker = asyncio.create_task(asyncio.to_thread(operation, token))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        token.cancel()
        cleanup = asyncio.gather(worker, return_exceptions=True)
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                token.cancel()
        raise
