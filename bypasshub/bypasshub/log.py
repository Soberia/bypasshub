import sys
import time
import threading
import multiprocessing
import logging
import logging.config
import logging.handlers
from pathlib import Path
from typing import Literal

from uvicorn.logging import ColourizedFormatter

from .config import config

log_size = config["log"]["size"]
log_storage = config["log"]["store"]
log_level = logging.getLevelName(config["log"]["level"].upper())
log_dir = Path(f"{config['log']['path']}")
if log_storage and not log_dir.exists():
    log_dir.mkdir(parents=True, exist_ok=True)


class _StorageFormatter(logging.Formatter):
    """Custom log formatter to use UTC time standard and control the traceback."""

    converter = time.gmtime

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._traceback = True

    def formatException(self, *args) -> str:
        return super().formatException(*args) if self._traceback else ""


class _ConsoleFormatter(ColourizedFormatter):
    """Custom log formatter to control the traceback."""

    def formatException(self, *args) -> str:
        return (
            super().formatException(*args) if config["log"]["stdout_traceback"] else ""
        )


class Process(multiprocessing.Process):
    """Custom `multiprocessing.Process` that logs the unhandled exceptions."""

    def run(self) -> None:
        try:
            super().run()
        except:
            uncaught_exception_handler(*sys.exc_info())


def uncaught_exception_handler(*args) -> None:
    """Logs the unhandled exceptions."""
    logger = logging.getLogger(__package__)
    exc_type = exc_value = exc_traceback = None
    if len(args) == 1:
        # When passed to the `threading.excepthook`
        exc_type = args[0].exc_type
        exc_value = args[0].exc_value
        exc_traceback = args[0].exc_traceback
    elif len(args) == 2:
        # When passed to the `asyncio.loop.set_exception_handler`
        exc = args[1].get("exception", args[1]["message"])
        exc_type = exc.__class__
        exc_value = exc
        exc_traceback = exc.__traceback__
    elif len(args) == 3:
        # When passed to the `sys.excepthook`
        exc_type, exc_value, exc_traceback = args

    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        # Avoiding traceback on `KeyboardInterrupt` and `SystemExit`.
        # To show the traceback, next line could be uncommented.
        # sys.__excepthook__(exc_type, exc_value, exc_traceback)
        if isinstance(exc_value, SystemExit) and exc_value.code == 0:
            return
        logger.warning("Application arbitrary killed by the user")
    else:
        logger.critical(exc_value, exc_info=(exc_type, exc_value, exc_traceback))


def modify_console_logger(enable: bool) -> None:
    """Modifies the console handler for the third-party loggers."""
    for handler in logging.getLogger(__package__).handlers:
        if handler.get_name() == "console":
            for logger_name in _config["loggers"].keys():
                if logger_name != __package__:
                    logger = logging.getLogger(logger_name)
                    if enable:
                        logger.addHandler(handler)
                    else:
                        logger.removeHandler(handler)

            break


def modify_handler(
    handler: Literal["console", "storage"],
    *,
    traceback: bool | None = None,
    level: int | str | None = None,
) -> None:
    """Modifies the log level or traceback status for the specified handler."""
    if traceback is not None or level is not None:
        for logger_name in _config["loggers"].keys():
            for _handler in logging.getLogger(logger_name).handlers:
                if _handler.get_name().startswith(handler):
                    if handler == "console":
                        config["log"]["stdout_traceback"] = traceback
                    else:
                        _handler.formatter._traceback = traceback

                    if level:
                        _handler.setLevel(level)

                    break


_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "()": _ConsoleFormatter,
            "format": "%(levelprefix)s [%(name)s] %(message)s",
        },
        "storage": {
            "()": _StorageFormatter,
            "format": "%(asctime)s | %(process)d | %(levelname)s | %(name)s --> %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "level": logging.INFO,
            "stream": "ext://sys.stdout",
        },
        f"storage_{__package__}": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "storage",
            "level": log_level,
            "filename": log_dir.joinpath(f"{__package__}.log"),
            "mode": "a+",
            "maxBytes": 1048576,
            "backupCount": log_size,
        },
        "storage_uvicorn": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "storage",
            "level": log_level,
            "filename": log_dir.joinpath("uvicorn.log"),
            "mode": "a+",
            "maxBytes": 1048576,
            "backupCount": log_size,
        },
    },
    "loggers": {
        __package__: {
            "handlers": ["console", f"storage_{__package__}"],
            "level": logging.DEBUG,
        },
        "uvicorn.error": {
            "handlers": ["storage_uvicorn"],
            "level": logging.DEBUG,
        },
        "uvicorn.access": {
            "handlers": [],
            "level": logging.DEBUG,
        },
    },
}

# Preventing the logs to be stored on the disk
if not log_storage:
    for logger in _config["loggers"].values():
        for handler in (handlers := logger["handlers"]):
            if handler.startswith("storage"):
                handlers.remove(handler)


# Attaching custom exception handler for logging the
# uncaught exceptions in the main and derived threads.
# NOTE: Handler also should be attached on AsyncIO's event
#       loop on it's creation.
sys.excepthook = threading.excepthook = uncaught_exception_handler
logging.config.dictConfig(_config)
