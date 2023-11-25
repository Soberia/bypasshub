import asyncio
import importlib
from typing import NoReturn

from bypasshub import log
from bypasshub.cli import CLI
from bypasshub.utils import create_event_loop


async def main() -> None:
    log.setup()

    if await CLI():
        return

    # Delaying the import for faster CLI responses
    await importlib.import_module("bypasshub.app").run()


def run() -> NoReturn:
    with asyncio.Runner(loop_factory=create_event_loop) as runner:
        runner.run(main())


if __name__ == "__main__":
    run()
