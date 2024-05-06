import logging
import argparse
from typing import Any
from contextlib import suppress
from collections.abc import Sequence

import orjson
from click import style

from . import __version__
from . import errors
from .utils import gather
from .errors import BaseError
from .managers import Manager
from .database import Database
from .log import modify_console_logger, modify_handler

logger = logging.getLogger(__name__)


class UsernameAction(argparse.Action):
    """Custom action which only stores the unique values."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        setattr(namespace, self.dest, set(values))


class DateAction(argparse.Action):
    """Custom action which converts the value to the integer if possible."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        with suppress(ValueError):
            values = int(values)

        setattr(namespace, self.dest, values)


class ArgumentParser(argparse.ArgumentParser):
    """Custom argument parser which capitalizes the output message."""

    class _ArgumentGroup(argparse._ArgumentGroup):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.title = self.title and self.title.title()

    class _HelpFormatter(argparse.RawDescriptionHelpFormatter):
        def _format_usage(self, *args, **kwargs) -> str:
            return super()._format_usage(*args, **kwargs).replace("usage:", "Usage:", 1)

        def _format_action(self, action: argparse.Action) -> str:
            parts = super()._format_action(action)
            if action.nargs == argparse.PARSER:
                parts = "\n".join(parts.split("\n")[1:])
            return parts

        def _format_action_invocation(self, action: argparse.Action) -> str:
            action.help = action.help and (action.help[0].upper() + action.help[1:])
            formatted = super()._format_action_invocation(action)

            # Only keeping the last `metavar`
            if action.option_strings and action.nargs != 0:
                formatted = formatted.replace(
                    f" {
                        self._format_args(
                            action, self._get_default_metavar_for_optional(action)
                        )
                    }",
                    "",
                    len(action.option_strings) - 1,
                )

            return formatted

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, formatter_class=self._HelpFormatter)

    def add_argument_group(self, *args, **kwargs) -> _ArgumentGroup:
        group = self._ArgumentGroup(self, *args, **kwargs)
        self._action_groups.append(group)
        return group


class CLI:
    """The command line interface.

    Returns:
        Whether any command is executed.
    """

    def __await__(self) -> bool:
        return self._run().__await__()

    def _setup_parser(self) -> None:
        self._parser = parser = ArgumentParser(
            prog=__package__,
            epilog="Run '%(prog)s COMMAND --help' for more information on a command",
        )

        parser.add_argument(
            "-v", "--version", action="version", version=f"%(prog)s {__version__}"
        )
        parser.add_argument(
            "--debug", "--verbose", action="store_true", help="Show more log"
        )

        subparser = parser.add_subparsers(
            title="commands", dest="command", metavar="[command]"
        )
        self._user = user = subparser.add_parser("user", help="Manage the users")
        self._plan = plan = subparser.add_parser("plan", help="Update the user's plan")
        self._reserved_plan = reserved_plan = subparser.add_parser(
            "reserved-plan", help="Update the user's reserved plan"
        )
        self._info = info = subparser.add_parser("info", help="Get the users' info")
        self._database = database = subparser.add_parser(
            "database", help="Manage the database"
        )

        username_arguments = {
            "action": UsernameAction,
            "nargs": "+",
            "help": "The user's username. Multiple usernames could be specified",
        }

        user.add_argument("username", **username_arguments)
        user.add_argument("-a", "--add", action="store_true", help="Add a user")
        user.add_argument("-d", "--delete", action="store_true", help="Delete a user")
        user.add_argument(
            "--force",
            action="store_true",
            help=(
                "Ignore failures to reflect the changes to the services"
                " and perform the action anyway"
            ),
        )
        user.add_argument(
            "--reset-total-traffic",
            action="store_true",
            help="Reset the user's total traffic consumption",
        )
        plan.add_argument("username", **username_arguments)
        plan.add_argument(
            "-s",
            "--start-date",
            action=DateAction,
            metavar="<DATE | INT>",
            help=(
                "The plan start date in ISO 8601 format or UNIX timestamp."
                " If not specified, no time restriction will be applied"
            ),
        )
        plan.add_argument(
            "-d",
            "--duration",
            type=int,
            metavar="<INT>",
            help="The plan duration in seconds",
        )
        plan.add_argument(
            "-t",
            "--traffic",
            type=int,
            metavar="<INT>",
            help=(
                "The plan traffic limit in bytes."
                " If not specified, no traffic restriction will be applied"
            ),
        )
        plan.add_argument(
            "-e",
            "--extra-traffic",
            type=int,
            metavar="<INT>",
            help=(
                "The plan extra traffic limit in bytes."
                " If user's plan traffic limit is reached, this value will be consumed"
                " instead for managing the user's traffic usage"
            ),
        )
        plan.add_argument(
            "--reset-extra-traffic",
            default=None,
            action="store_true",
            help="Reset the extra traffic limit",
        )
        plan.add_argument(
            "--preserve-traffic",
            default=None,
            action="store_true",
            help="Do not reset the recorded traffic usage from the previous plan",
        )
        reserved_plan.add_argument("username", **username_arguments)
        reserved_plan.add_argument(
            "-d",
            "--duration",
            type=int,
            metavar="<INT>",
            help=(
                "The reserved plan duration in seconds."
                " If not specified, no time restriction will be applied"
            ),
        )
        reserved_plan.add_argument(
            "-t",
            "--traffic",
            type=int,
            metavar="<INT>",
            help=(
                "The reserved plan traffic limit in bytes."
                " If not specified, no traffic restriction will be applied"
            ),
        )
        reserved_plan.add_argument(
            "--remove",
            default=None,
            action="store_true",
            help="Remove the reserved plan",
        )
        info.add_argument(
            "-u", "--users", action="store_true", help="Show all the users"
        )
        info.add_argument(
            "-c", "--capacity", action="store_true", help="Show count of all the users"
        )
        info.add_argument(
            "-a",
            "--active-capacity",
            action="store_true",
            help="Show count of all the users that have an active plan",
        )
        info.add_argument(
            "--credentials",
            metavar="<USERNAME>",
            help="Show the user's credentials",
        )
        info.add_argument("--plan", metavar="<USERNAME>", help="Show the user's plan")
        info.add_argument(
            "--reserved-plan",
            metavar="<USERNAME>",
            help="Show the user's reserved plan",
        )
        info.add_argument(
            "--plan-history",
            metavar=("<USERNAME>", "<ID>"),
            nargs="+",
            help="Show the user's plan history",
        )
        info.add_argument(
            "--total-traffic",
            metavar="<USERNAME>",
            help="Show the user's total traffic consumption in bytes",
        )
        info.add_argument(
            "--latest-activity",
            metavar="<USERNAME>",
            help="Show the user's latest activity date",
        )
        info.add_argument(
            "--latest-activities",
            action=DateAction,
            metavar="<DATE | INT>",
            nargs="?",
            const="",
            help=(
                "Show the latest activity date of all the users."
                " If the date range in ISO 8601 format or UNIX timestamp specified,"
                " only the activity dates beyond the specified date will be included"
            ),
        )
        info.add_argument(
            "--is-exist",
            metavar="<USERNAME>",
            help="Show whether the user exists in the database",
        )
        info.add_argument(
            "--has-active-plan",
            metavar="<USERNAME>",
            help=(
                "Show whether the user has an active plan."
                " A plan is considered active when still has time and traffic"
            ),
        )
        info.add_argument(
            "--has-active-plan-time",
            metavar="<USERNAME>",
            help="Show whether the user has a plan with remained time",
        )
        info.add_argument(
            "--has-active-plan-traffic",
            metavar="<USERNAME>",
            help="Show whether the user has a plan with remained traffic",
        )
        info.add_argument(
            "--has-unlimited-time",
            metavar="<USERNAME>",
            help="Show whether the user has an unrestricted time plan",
        )
        info.add_argument(
            "--has-unlimited-traffic",
            metavar="<USERNAME>",
            help="Show whether the user has an unrestricted traffic plan",
        )
        info.add_argument(
            "--has-no-capacity",
            action="store_true",
            help=(
                "Show whether the count of all the users"
                " is bigger than the capacity limit"
            ),
        )
        info.add_argument(
            "--has-no-active-capacity",
            action="store_true",
            help=(
                "Show whether the count of all the users that have"
                " an active plan is bigger than the capacity limit"
            ),
        )
        info.add_argument(
            "--subscription",
            metavar="<USERNAME>",
            help="Generate 'Xray-core' config URLs for the user",
        )
        database.add_argument(
            "-s",
            "--sync",
            action="store_true",
            help="Manually synchronize the services with the database",
        )
        database.add_argument(
            "-d",
            "--dump",
            action="store_true",
            help="Dump the database as JSON to the STDOUT",
        )
        database.add_argument(
            "-b",
            "--backup",
            metavar="<SUFFIX>",
            nargs="?",
            const="",
            help="Generate and store a database backup (default: %%timestamp%%.bak)",
        )

    def _log(
        self,
        exception: Exception,
        *,
        traceback: bool | None = None,
        log_sync: bool | None = None,
    ) -> None:
        for error in (
            exception.exceptions
            if isinstance(exception, ExceptionGroup)
            else (exception,)
        ):
            if log_sync or not isinstance(
                error,
                errors.SynchronizationError,  # already logged
            ):
                if isinstance(error, errors.StateSynchronizerTimeout):
                    error.message += f" (is '{__package__}' running?)"
                    traceback = False

                logger.exception(
                    repr(error) if isinstance(error, BaseError) else error,
                    exc_info=error if traceback else None,
                )

    async def _exec(self, command: str) -> None:
        arguments = self._arguments
        async with Manager(skip_retry=True) as manager:
            try:
                match command:
                    case "user":
                        if arguments.add:
                            (credentials, exceptions) = await gather([
                                manager.add_user(username, force=arguments.force)
                                for username in arguments.username
                            ])

                            for exception in exceptions:
                                if isinstance(exception, errors.SynchronizationError):
                                    credentials.append(exception.payload)
                                self._log(exception)

                            if credentials:
                                print(
                                    style(f"{'Users Credentials':-^42}", fg="cyan"),
                                    "\n".join([
                                        f"{credential['username']}@{credential['uuid']}"
                                        for credential in credentials
                                    ]),
                                    sep="\n",
                                )
                        elif arguments.delete:
                            for exception in (
                                await gather([
                                    manager.delete_user(username, force=arguments.force)
                                    for username in arguments.username
                                ])
                            )[1]:
                                self._log(exception)
                        elif arguments.reset_total_traffic:
                            for username in arguments.username:
                                manager.reset_total_traffic(username)
                        else:
                            self._user.print_help()
                    case "plan":
                        for exception in (
                            await gather([
                                manager.update_plan(
                                    username,
                                    start_date=arguments.start_date,
                                    duration=arguments.duration,
                                    traffic=arguments.traffic,
                                    extra_traffic=arguments.extra_traffic,
                                    reset_extra_traffic=arguments.reset_extra_traffic,
                                    preserve_traffic_usage=arguments.preserve_traffic,
                                )
                                for username in arguments.username
                            ])
                        )[1]:
                            self._log(exception)
                    case "reserved-plan":
                        for username in arguments.username:
                            try:
                                if arguments.remove:
                                    manager.unset_reserved_plan(username)
                                else:
                                    manager.set_reserved_plan(
                                        username,
                                        duration=arguments.duration,
                                        traffic=arguments.traffic,
                                    )
                            except Exception as error:
                                self._log(error)
                    case "info":
                        if arguments.users:
                            print(*manager.usernames, sep="\n")
                        elif arguments.capacity:
                            print(manager.capacity)
                        elif arguments.active_capacity:
                            print(manager.active_capacity)
                        elif username := arguments.credentials:
                            credentials = manager.get_credentials(username)
                            print(f"{credentials['username']}@{credentials['uuid']}")
                        elif username := arguments.plan:
                            print(
                                *[
                                    (
                                        f"{key.replace('plan_', '').replace('_', '-')}:"
                                        f" {'-' if value is None else value}"
                                    )
                                    for key, value in manager.get_plan(username).items()
                                ],
                                sep="\n",
                            )
                        elif username := arguments.reserved_plan:
                            if reserved_plan := manager.get_reserved_plan(username):
                                print(
                                    *[
                                        (
                                            f"{key.replace('plan_', '').replace('_', '-')}:"
                                            f" {'-' if value is None else value}"
                                        )
                                        for key, value in reserved_plan.items()
                                    ],
                                    sep="\n",
                                )
                        elif args := arguments.plan_history:
                            separator = style(f"{'':-^42}", fg="cyan")
                            for record in (
                                history := manager.get_plan_history(
                                    args[0], id=args[1] if len(args) == 2 else None
                                )
                            ):
                                print(
                                    *[
                                        (
                                            f"{key.replace('plan_', '').replace('_', '-')}:"
                                            f" {'-' if value is None else value}"
                                        )
                                        for key, value in record.items()
                                    ],
                                    sep="\n",
                                )
                                if record is not history[-1]:
                                    print(separator)
                        elif username := arguments.total_traffic:
                            print(
                                *[
                                    f"{key}: {value}"
                                    for key, value in manager.get_total_traffic(
                                        username
                                    ).items()
                                ],
                                sep="\n",
                            )
                        elif username := arguments.latest_activity:
                            if latest_activity := manager.get_latest_activity(username):
                                print(latest_activity)
                        elif (from_date := arguments.latest_activities) is not None:
                            if latest_activities := manager.get_latest_activities(
                                from_date or None
                            ):
                                print(
                                    *[
                                        f"{key}: {value}"
                                        for key, value in latest_activities.items()
                                    ],
                                    sep="\n",
                                )
                        elif username := arguments.is_exist:
                            print(manager.is_exist(username))
                        elif username := arguments.has_active_plan:
                            print(manager.has_active_plan(username))
                        elif username := arguments.has_active_plan_time:
                            print(manager.has_active_plan_time(username))
                        elif username := arguments.has_active_plan_traffic:
                            print(manager.has_active_plan_traffic(username))
                        elif username := arguments.has_unlimited_time:
                            print(manager.has_unlimited_time_plan(username))
                        elif username := arguments.has_unlimited_traffic:
                            print(manager.has_unlimited_traffic_plan(username))
                        elif arguments.has_no_capacity:
                            print(manager.has_no_capacity())
                        elif arguments.has_no_active_capacity:
                            print(manager.has_no_active_capacity())
                        elif username := arguments.subscription:
                            print(
                                manager._xray.generate_subscription(
                                    manager.get_credentials(username)["uuid"]
                                )
                            )
                        else:
                            self._info.print_help()
                    case "database":
                        if arguments.sync:
                            try:
                                if not manager.connected:
                                    manager.connect()
                                print(
                                    "Services are"
                                    f" {'synced' if (await manager.sync()) else 'in sync'}"
                                )
                            except Exception as error:
                                self._log(error, log_sync=True)
                        elif arguments.dump:
                            print(
                                orjson.dumps(
                                    Database.dump(), option=orjson.OPT_INDENT_2
                                ).decode()
                            )
                        elif (suffix := arguments.backup) is not None:
                            Database.backup(suffix and f".{suffix}")
                            print("Database backup is located in: ./database/backup")
                        else:
                            self._database.print_help()
            except Exception as error:
                self._log(error, traceback=True)
                self._parser.exit(1)

    async def _run(self) -> bool:
        self._setup_parser()
        self._arguments = self._parser.parse_args()
        if self._arguments.debug:
            modify_console_logger(True)
            modify_handler(
                "console", level=logging.DEBUG, traceback=True, console_timestamp=False
            )
        else:
            modify_handler("console", console_timestamp=False)
            # Temporarily avoiding to store the traceback
            modify_handler("storage", traceback=False)

        executed = False
        if command := self._arguments.command:
            await self._exec(command)
            executed = True

        modify_handler("console", console_timestamp=True)
        if not self._arguments.debug:
            modify_handler("storage", traceback=True)

        return executed
