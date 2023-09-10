import sys
import math
import asyncio
import inspect
import multiprocessing
from typing import Any
from datetime import datetime, timezone
from collections.abc import Iterable

import uvloop

from .log import uncaught_exception_handler


class Process(multiprocessing.Process):
    """Custom ``multiprocessing.Process`` that logs the unhandled exceptions."""

    def run(self) -> None:
        try:
            if self._target:
                if inspect.iscoroutinefunction(self._target):
                    with asyncio.Runner(loop_factory=create_event_loop) as runner:
                        runner.run(self._target(*self._args, **self._kwargs))
                else:
                    self._target(*self._args, **self._kwargs)
        except:
            uncaught_exception_handler(*sys.exc_info())


def create_event_loop() -> uvloop.Loop:
    """Creates the AsyncIO event loop."""
    loop = uvloop.new_event_loop()
    loop.set_exception_handler(uncaught_exception_handler)
    asyncio.set_event_loop(loop)

    return loop


def convert_size(size: int, precision: int = 2) -> str:
    """Converts the input value in bytes to a bigger unit."""
    if size == 0:
        return "0B"

    unit = int(math.floor(math.log(size, 1024)))
    return (
        str(round(size / math.pow(1024, unit), precision or None))
        + ("B", "KiB", "MiB", "GiB", "TiB", "PiB")[unit]
    )


def current_time() -> datetime:
    """Returns the current time in the UTC timezone."""
    return datetime.now(timezone.utc).replace(microsecond=0)


async def gather(iterable: Iterable) -> tuple[list[Any], list[Exception]]:
    """
    Wrapper around ``asyncio.gather()`` that
    separates the exceptions from the results.
    """
    returns = []
    exceptions = []
    for result in await asyncio.gather(*iterable, return_exceptions=True):
        (exceptions if isinstance(result, Exception) else returns).append(result)

    return (returns, exceptions)
