import asyncio
import logging
import sqlite3
from os import PathLike
from pathlib import Path

import orjson

from .config import config
from .utils import current_time
from .type import DatabaseSchema

backup_interval = config["database"]["backup_interval"]
database_path = Path(config["database"]["path"])
backup_dir = database_path.with_name("backup")
logger = logging.getLogger(__name__)


class Database:
    """The interface to manage the database.

    Attributes:
        `BACKUP_ENABLED`: Whether the auto backup is enabled.

    Returns:
        The database connection object that can be used
        to interact with the database.
    """

    __initiated = None
    __backup_task = None
    BACKUP_ENABLED = backup_interval > 0

    def __new__(cls) -> sqlite3.Connection:
        database = super().__new__(cls)
        database.__init__()
        return database.connection

    def __init__(self) -> None:
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = lambda cursor, row: {
            key: value
            for key, value in zip([column[0] for column in cursor.description], row)
        }
        if not Database.__initiated:
            if backup_interval == 0:
                logger.debug("The database backup procedure is disabled")
            self._initiate()

    def _initiate(self) -> None:
        """Creates the database and its required tables."""
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(
            """
            BEGIN;
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(64),
                uuid TEXT UNIQUE,
                user_creation_date TEXT,
                plan_start_date TEXT,
                plan_duration INT, /* in seconds */
                plan_traffic BIGINT, /* in bytes */
                plan_traffic_usage BIGINT DEFAULT 0, /* in bytes */
                plan_extra_traffic BIGINT DEFAULT 0, /* in bytes */
                plan_extra_traffic_usage BIGINT DEFAULT 0, /* in bytes */
                total_upload BIGINT DEFAULT 0, /* in bytes */
                total_download BIGINT DEFAULT 0, /* in bytes */
                PRIMARY KEY (username)
            );
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER UNIQUE,
                date TEXT,
                username VARCHAR(64),
                plan_start_date TEXT,
                plan_duration INT, /* in seconds */
                plan_traffic BIGINT, /* in bytes */
                plan_extra_traffic BIGINT, /* in bytes */
                FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
            );
            COMMIT;
            """
        )

    @staticmethod
    def dump(path: PathLike | None = None) -> DatabaseSchema:
        """Returns the current state of the database as a dictionary.

        Args:
            `path`: The location to store the dumb file as `JSON`.
        """
        database = Database()
        try:
            output = {
                table["name"]: database.execute(
                    f"SELECT * FROM {table['name']}"
                ).fetchall()
                for table in database.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        finally:
            database.close()

        if path:
            with open(path, "wb") as file:
                file.write(orjson.dumps(output, option=orjson.OPT_INDENT_2))
        return output

    @staticmethod
    def backup(suffix: str | None = None) -> None:
        """Creates a backup of the database.

        Args:
            `suffix`:
                The backup file name suffix.
                If omitted, `%timestamp%.bak` will be used.
        """
        if not suffix:
            suffix = f"{current_time().strftime(r'.%Y%m%d%H%M%S')}.bak"

        if not backup_dir.exists():
            backup_dir.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(
            backup_dir.joinpath(f"{database_path.name}{suffix}")
        ) as db:
            _db = Database()
            _db.backup(db)
            _db.close()

        db.close()

    @staticmethod
    def start_backup() -> asyncio.Task | None:
        """Starts the database backup procedure.

        The backup interval can be configured with `backup_interval`
        property in the configuration file.

        Returns:
            The related AsyncIO Task that can be awaited on.

        Raises:
            ``RuntimeError``:
                When called while the procedure is already running.
        """
        if Database.__backup_task is not None:
            raise RuntimeError("The database backup procedure is already running")
        elif backup_interval <= 0:
            return

        async def _backup() -> None:
            logger.info("The database backup procedure is started")
            while True:
                try:
                    await asyncio.sleep(backup_interval)
                    Database.backup()
                except asyncio.CancelledError:
                    logger.info("The database backup procedure is stopped")
                    raise

        Database.__backup_task = asyncio.create_task(_backup(), name="database_backup")
        return Database.__backup_task

    @staticmethod
    def stop_backup() -> None:
        """Stops the database backup procedure."""
        if (task := Database.__backup_task) is not None and not task.cancelled():
            task.cancel()
            Database.__backup_task = None
