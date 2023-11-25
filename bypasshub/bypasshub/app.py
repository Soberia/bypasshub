import asyncio
import logging

from . import __version__
from .utils import Process
from .managers import Users
from .cleanup import Cleanup
from .monitor import Monitor
from .database import Database
from .api.app import run as api

logger = logging.getLogger(__name__)


async def run() -> None:
    """Runs the app."""
    logger.info(f"{__package__} v{__version__} is started")

    # The services are in a waiting state for list of the
    # users to be generated. Prioritizing the generation of
    # this list to speed up the starting time of the services.
    with Users() as users:
        users.generate_list()

    Process(target=api, daemon=True, name=f"{__package__}_api").start()

    cleanup = Cleanup()
    monitor = Monitor()
    cleanup.add(monitor.stop)
    if Database.BACKUP_ENABLED:
        cleanup.add(Database.stop_backup)
        await asyncio.wait([monitor.start(), Database.start_backup()])
    else:
        await monitor.start()
