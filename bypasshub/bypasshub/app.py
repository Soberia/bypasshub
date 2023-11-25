import asyncio
import logging

from . import __version__
from .utils import Process
from .cleanup import Cleanup
from .monitor import Monitor
from .database import Database
from .api.app import run as api

logger = logging.getLogger(__name__)


async def run() -> None:
    """Runs the app."""
    logger.info(f"{__package__} v{__version__} is started")

    Process(target=api, daemon=True, name="api").start()

    cleanup = Cleanup()
    monitor = Monitor()
    cleanup.add(monitor.stop)
    if Database.BACKUP_ENABLED:
        cleanup.add(Database.stop_backup)
        await asyncio.wait([monitor.start(), Database.start_backup()])
    else:
        await monitor.start()
