import asyncio
import importlib
from typing import NoReturn

from bypasshub import log
from bypasshub.cli import CLI
from bypasshub.utils import create_event_loop, is_duplicated_instance


async def main() -> None:
    log.setup()

    if await CLI():
        return

    if is_duplicated_instance():
        raise RuntimeError(
            f"Only one instance of '{__package__}' should run at the same time"
        )

    # Delaying the import for faster CLI responses
    await importlib.import_module("bypasshub.app").run()


def run() -> NoReturn:
    with asyncio.Runner(loop_factory=create_event_loop) as runner:
        runner.run(main())


if __name__ == "__main__":
    run()
