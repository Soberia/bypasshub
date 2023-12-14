import os
import sys
import asyncio
import logging
import inspect
import multiprocessing
from typing import Self
from signal import Signals, SIGINT, SIGTERM
from collections.abc import Callable

logger = logging.getLogger(__name__)


class Cleanup:
    """
    Clean up handler that runs registered tasks on application
    termination by the `SIGINT` or `SIGTERM` signals.
    """

    __pid = None
    __instance = None
    __callbacks = set()

    def __new__(cls) -> Self:
        process = multiprocessing.current_process()
        if (pid := Cleanup.__pid) != process.pid:
            Cleanup.__pid = process.pid
            if pid is not None and len(Cleanup.__callbacks):
                # Parent processes forked this process.
                # Previous tasks should be ignored.
                Cleanup.__callbacks.clear()

            Cleanup.__instance = super().__new__(cls)
            Cleanup.__instance._is_cleaning = None
            Cleanup.__instance._process_name = process.name
            Cleanup.__instance._is_main_process = process.name == "MainProcess"
            Cleanup.__instance.log = (
                # Preventing duplicated logs on subprocesses
                Cleanup.__instance._is_main_process
            )
            Cleanup.__instance._listen()

        return Cleanup.__instance

    async def _handler(self, signal: Signals) -> None:
        if self._is_cleaning is None:
            self._is_cleaning = True

            callbacks = []
            async_callbacks = []
            for callback in self.__callbacks:
                (
                    async_callbacks
                    if inspect.iscoroutinefunction(callback)
                    or inspect.isawaitable(callback)
                    else callbacks
                ).append(callback)

            if callbacks or async_callbacks:
                if self._log:
                    message = "Waiting for the scheduled tasks to finish"
                    if signal == SIGINT:
                        message += " (Ctrl+C to skip)"
                    logger.info(message)

                # Waiting for the child processes to terminate
                if self._is_main_process:
                    processes = []
                    for process in multiprocessing.active_children():
                        if process.name.startswith(__package__) and process.is_alive():
                            processes.append(process)
                            # The `SIGINT` signals initiated with Ctrl+C from the
                            # terminal will be propagated to all the child processes
                            # by default. The `SIGTERM` signal should be propagated.
                            if signal != SIGINT:
                                os.kill(process.pid, signal)

                    for process in processes:
                        if process.is_alive():
                            process.join()

                if callbacks:
                    for callback in callbacks:
                        callback()
                if async_callbacks:
                    await asyncio.gather(*[callback() for callback in async_callbacks])

                logger.debug(
                    f"The scheduled tasks are finished successfully{
                        "" if self._is_main_process else f" (in '{self._process_name}')"
                    }"
                )

            self._is_cleaning = False
            if self._is_main_process:
                sys.exit(os.EX_OK)
            os._exit(os.EX_OK)
        else:
            if self._log and self._is_cleaning is not False:
                logger.warning("The pending tasks are cancelled")

            if self._is_main_process:
                sys.exit(signal)
            os._exit(signal)

    def _listen(self) -> None:
        # For an unknown reason, storing the event loop inside a variable and
        # access it inside a for-loop will override the first signal handler!
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(
            SIGINT, lambda: asyncio.create_task(self._handler(SIGINT))
        )
        loop.add_signal_handler(
            SIGTERM, lambda: asyncio.create_task(self._handler(SIGTERM))
        )

    @staticmethod
    def add(callback: Callable) -> None:
        """Adds a callback function to the scheduled tasks."""
        Cleanup.__callbacks.add(callback)

    @staticmethod
    def remove(callback: Callable) -> None:
        """Removes a callback function from the scheduled tasks."""
        try:
            Cleanup.__callbacks.remove(callback)
        except KeyError:
            pass

    @property
    def is_cleaning(self) -> bool:
        """The clean up process running status at the current time."""
        return bool(self._is_cleaning)

    @property
    def log(self) -> bool:
        """The log status.

        By default, it's equal to `False` if this is not the main process.
        The value could be modified. However, that leads to duplicated logs
        if the clean up handler is running in multiple processes.
        """
        return self._log

    @log.setter
    def log(self, value: bool) -> None:
        self._log = value
