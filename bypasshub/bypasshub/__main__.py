import asyncio
from typing import NoReturn

from bypasshub import log
from bypasshub.cli import CLI
from bypasshub.cleanup import Cleanup
from bypasshub.monitor import Monitor
from bypasshub.database import Database
from bypasshub.utils import Process, create_event_loop


async def main() -> None:
    log.setup()

    if await CLI():
        return

    # Delaying the import for faster CLI responses
    from bypasshub.api.app import run as api

    Process(target=api, daemon=True, name="api").start()

    cleanup = Cleanup()
    monitor = Monitor()
    monitor.generate_list()
    cleanup.add(monitor.stop)
    if Database.BACKUP_ENABLED:
        cleanup.add(Database.stop_backup)
        await asyncio.wait([monitor.start(), Database.start_backup()])
    else:
        await monitor.start()


def run() -> NoReturn:
    with asyncio.Runner(loop_factory=create_event_loop) as runner:
        runner.run(main())


if __name__ == "__main__":
    run()
