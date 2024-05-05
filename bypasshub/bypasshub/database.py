import asyncio
import logging
import sqlite3
from os import PathLike
from pathlib import Path

import orjson

from .config import config
from .types import DatabaseSchema
from .utils import current_time, convert_size

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
        self.connection = sqlite3.connect(database_path, autocommit=False)
        self.connection.row_factory = lambda cursor, row: {
            key: value
            for key, value in zip([column[0] for column in cursor.description], row)
        }

        # It's not possible to enable the following pragmas within a transaction
        self.connection.autocommit = True
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.autocommit = False

        if not Database.__initiated:
            if backup_interval == 0:
                logger.debug("The database backup procedure is disabled")
            self._initiate()

    def _initiate(self) -> None:
        """Creates the database and its required tables."""
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(64),
                uuid TEXT UNIQUE,
                user_creation_date TEXT,
                user_latest_activity_date TEXT,
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
            CREATE TABLE IF NOT EXISTS reserved_plans (
                username VARCHAR(64),
                plan_reserved_date TEXT,
                plan_duration INT, /* in seconds */
                plan_traffic BIGINT, /* in bytes */
                PRIMARY KEY (username)
                FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER,
                date TEXT,
                action VARCHAR(64),
                username VARCHAR(64),
                plan_start_date TEXT,
                plan_duration INT, /* in seconds */
                plan_traffic BIGINT, /* in bytes */
                plan_extra_traffic BIGINT, /* in bytes */
                FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
            );
            """
        )
        self.connection.commit()

    @staticmethod
    def size(database: sqlite3.Connection) -> int:
        """Returns the database size in bytes."""
        result = database.execute(
            """
            SELECT page_count * page_size as size
            FROM pragma_page_count(), pragma_page_size()
            """
        ).fetchone()

        if database.autocommit == False:
            database.commit()

        return result["size" if type(result) is dict else 0]

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

        backup_name = f"{database_path.name}{suffix}"
        with sqlite3.connect(
            backup_dir.joinpath(backup_name),
            # It's not possible to perform `VACUUM`
            # command within a transaction
            autocommit=True,
        ) as db:
            # It seems `backup()` method (and then `VACUUM` command)
            # do not blocks the original database's transactions so
            # it's favored over `VACUUM INTO` command.
            _db = Database()
            _db.backup(db)
            _db.close()
            previous_size = Database.size(db)
            db.execute("VACUUM")
            reduced = previous_size - Database.size(db)

        db.close()
        logger.debug(
            f"The database backup file '{backup_name}' is created{
                f" (file size reduced by '{convert_size(reduced)}')"
                if reduced > 0
                else ""
            }"
        )

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
