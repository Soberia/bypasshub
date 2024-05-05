import os
import sys
import math
import fcntl
import asyncio
import inspect
import multiprocessing
from typing import Any
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections.abc import Iterable

import uvloop

from .config import config
from .cleanup import Cleanup
from .types import DataUnits, TimeUnits
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
        except BaseException:
            uncaught_exception_handler(*sys.exc_info())


def create_event_loop() -> uvloop.Loop:
    """Creates the AsyncIO event loop."""
    loop = uvloop.new_event_loop()
    loop.set_exception_handler(uncaught_exception_handler)
    asyncio.set_event_loop(loop)

    return loop


def is_duplicated_instance() -> bool:
    """Whether there are other running instance of the application."""
    lock_path = Path(config["main"]["temp_path"]).joinpath("lock")
    lock = os.open(lock_path, os.O_WRONLY | os.O_CREAT)

    try:
        fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        Cleanup.add(
            # Gracefully unlock and remove the lock file
            lambda: fcntl.lockf(lock, fcntl.LOCK_UN) is None
            and lock_path.unlink(missing_ok=True)
        )
        return False
    except IOError:
        return True


def convert_size(
    size: int,
    precision: int = 2,
    *,
    separator: str = "",
    units: DataUnits | None = None,
) -> str:
    """Approximately converts the input value in bytes to a bigger decimal unit prefix.

    Args:
        `separator`: The unit separator character.

        `units`: The map of the data unit abbreviations to custom names.
    """
    prefixes = ("B", "kB", "MB", "GB", "TB", "PB")
    if size == 0:
        return f"0{separator}{units['B'] if units else prefixes[0]}"

    magnitude = int(math.floor(math.log(size, 1000)))
    unit = prefixes[magnitude]
    return "".join((
        str(round(size / math.pow(1000, magnitude), precision or None)),
        separator,
        units[unit] if units else unit,
    ))


def convert_time(
    time: timedelta | int, *, separator: str = "", units: TimeUnits | None = None
) -> str:
    """Approximately converts the input value in seconds to a bigger unit.

    Args:
        `separator`: The unit separator character.

        `units`: The map of the time unit abbreviations to custom names.
    """
    if not isinstance(time, timedelta):
        time = timedelta(seconds=time)
    if not units:
        unit = ("d", "h", "m", "s")
        units = dict(zip(unit, unit))

    if time.days:
        return f"{time.days}{separator}{units['d']}"
    elif (seconds := time.seconds) >= 3600:
        return f"{int(seconds / 3600)}{separator}{units['h']}"
    elif seconds >= 60:
        return f"{int(seconds / 60)}{separator}{units['m']}"
    else:
        return f"{seconds}{separator}{units['s']}"


def convert_date(date: datetime | str | int | float) -> datetime:
    """
    Converts the given value in ISO 8601 format or UNIX timestamp to the
    `datetime` with the UTC time zone and stripped milliseconds.
    """
    if (date_type := type(date)) is not datetime:
        if date_type is str:
            date = datetime.fromisoformat(date)
        elif date_type in (int, float):
            date = datetime.fromtimestamp(date, tz=timezone.utc)

    if date.tzinfo != timezone.utc:
        date = date.astimezone(timezone.utc)

    return date.replace(microsecond=0)


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
