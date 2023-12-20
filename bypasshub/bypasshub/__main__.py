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

    # Imports are delayed for faster CLI responses

    # The services are in a waiting state for list of the
    # users to be generated. Prioritizing the generation of
    # this list to speed up the starting time of the services.
    with importlib.import_module("bypasshub.managers").Users() as users:
        users.generate_list()

    await importlib.import_module("bypasshub.app").run()


def run() -> NoReturn:
    asyncio.run(main(), loop_factory=create_event_loop)


if __name__ == "__main__":
    run()
