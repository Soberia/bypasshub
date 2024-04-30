import time
import logging
from pathlib import Path
from threading import Lock
from typing import Optional
from contextlib import suppress, contextmanager
from multiprocessing import current_process
from multiprocessing.process import AuthenticationString
from multiprocessing.managers import SyncManager, DictProxy
from collections.abc import Generator

from .. import errors
from ..config import config

CLIENT_TIMEOUT = 3  # seconds
CLIENT_RETRY_DELAY = 0.001  # seconds
RESERVED_NAME = "_global_lock"

socket_path = Path(config["main"]["temp_path"]).joinpath("manager.sock")
logger = logging.getLogger(__name__)

# Apparently, `SyncManager` doesn't read the authentication
# key from the passed `authkey` argument and clients cannot
# connect to the server with `AuthenticationError` while the
# value is not `None`.
# Directly modifying the process's authentication key instead.
current_process().authkey = AuthenticationString(config["api"]["key"])
_state = {}
_synchronizer = SyncManager(address=str(socket_path))
_synchronizer.register("state", lambda: _state, DictProxy)


class State[T]:
    """The process state synchronizer for sharing data between different processes.

    To properly reassign connection errors, all state interactions
    should be wrapped inside of the ``self._access_state()`` method
    which is a context manager protocol.

    The ``self._state`` property should be used to modify the state.

    Attributes:
        `name`:
            The name of the state slot.
            `ValueError` will be raised if value is reserved.
    """

    __server_pid = None
    _server_started = None

    def __init__(self, name: str | None = None) -> None:
        self.name = name
        if self.name == RESERVED_NAME:
            raise ValueError(
                f"The 'name' parameter is set to reserved value '{self.name}'"
            )

        self._dict = _synchronizer.dict
        self._lock = _synchronizer.Lock
        self._state_proxy: DictProxy | None = None
        self._global_lock_proxy: Optional[Lock] = None
        self._connected = None

    @contextmanager
    def _access_state(self, silent: bool | None = None) -> Generator[None, None, None]:
        """Handles the state exceptions.

        Args:
            `silent`:
                If `True` provided, and the state cannot be accessed or modified,
                no exception will be raised.

        Raises:
            `RuntimeError`:
                When connection to the state synchronizer is not established.
            ``errors.StateSynchronizerTimeout``:
                When failed to communicate with process state synchronizer server.
        """
        if not silent and not self._connected:
            raise RuntimeError(
                "Connection to the state synchronizer is not established"
            )

        try:
            yield
        except KeyError:
            if not silent:
                raise
        except AttributeError:
            if not silent or self._connected:
                raise
        except errors.UNIX_SOCKET_FAILURE:
            if not silent:
                raise errors.StateSynchronizerTimeout()

    def _load_state(self) -> None:
        self._connected = True
        try:
            with self._access_state():
                self._state_proxy = _synchronizer.state()
                if RESERVED_NAME not in self._state_proxy:
                    self._global_lock_proxy = self._state_proxy[RESERVED_NAME] = (
                        self._lock()
                    )
                else:
                    self._global_lock_proxy = self._state_proxy[RESERVED_NAME]
        except Exception:
            self._connected = False
            raise

    def run(self) -> None:
        """Runs the process state synchronizer server.

        Raises:
            `RuntimeError`: When server is already running.
        """
        if State._server_started:
            raise RuntimeError("Process state synchronizer server is already running")

        if socket_path.is_socket():
            socket_path.unlink(missing_ok=True)
            logger.info("Removed the socket file from the previous session")

        _synchronizer.start()
        self._load_state()
        State.__server_pid = current_process().pid
        State._server_started = True
        logger.debug("Process state synchronizer server is started")

    def connect(
        self, timeout: int = CLIENT_TIMEOUT, *, skip_retry: bool | None = None
    ) -> None:
        """Establishes a connection to the process state synchronizer server.

        Args:
            `timeout`:
                The time in seconds to wait for the communications to the
                server to be finished.
                `ValueError` will be raised if value is not a positive number.

            `skip_retry`:
                If `True` provided, `timeout` parameter will be ignored and only
                tries once to connect to the process state synchronizer server.
                Otherwise, ``errors.StateSynchronizerTimeout`` will be raised
                if could not establish a connection to the server after passed
                period of time specified with `timeout` parameter.
        """
        if timeout <= 0:
            raise ValueError("The 'timeout' parameter should be greater than zero")
        elif self._connected:
            return

        if State.__server_pid == current_process().pid:
            # Client and server are in the same process,
            # no need to communicate through the socket
            self._load_state()
        else:
            elapsed = 0
            while True:
                try:
                    _synchronizer.connect()
                except errors.UNIX_SOCKET_FAILURE:
                    if skip_retry:
                        logger.debug(
                            "Retrying to connect to the process state"
                            " synchronizer server is skipped"
                        )
                        return
                    elif elapsed > timeout:
                        raise errors.StateSynchronizerTimeout()
                    time.sleep(CLIENT_RETRY_DELAY)
                    elapsed += CLIENT_RETRY_DELAY
                else:
                    self._load_state()
                    logger.debug("Connected to the process state synchronizer server")

                    break

    def close(self) -> None:
        """Closes the process state synchronizer server.

        Raises:
            `RuntimeError`:
                When the current process did not start the server.
        """
        if State._server_started:
            if State.__server_pid != current_process().pid:
                raise RuntimeError(
                    "Process state synchronizer server should be terminated"
                    " from the process that starts the server"
                )

            if self._state_proxy:
                with self._access_state():
                    self._state_proxy.clear()
                self._state_proxy = None
                self._global_lock_proxy = None

            with suppress(BrokenPipeError):
                _synchronizer.shutdown()

            State.__server_pid = None
            State._server_started = False
            logger.debug("Process state synchronizer server is stopped")

    @property
    def _state(self) -> T | None:
        """The state data.

        Should be used inside the ``self._access_state()``
        context manager block.
        """
        return self._state_proxy.get(self.name, None)

    @_state.setter
    def _state(self, value: T) -> None:
        self._state_proxy[self.name] = value

    @property
    def _global_lock(self) -> Optional[Lock]:
        """
        The global process lock to prevent race conditions
        between processes when modify the state.

        Should be used inside the ``self._access_state()``
        context manager block.
        """
        return self._global_lock_proxy

    @property
    def connected(self) -> bool:
        """
        Whether the connection to the process
        state synchronizer is established.
        """
        return self._connected
