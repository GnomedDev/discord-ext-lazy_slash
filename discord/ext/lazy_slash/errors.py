from typing import Optional

import discord
from discord.ext import commands


class ApplicationCommandRegistrationError(discord.ClientException):
    """An exception raised when a command cannot be converted to an
    application command.

    This inherits from :exc:`discord.ClientException`

    Attributes
    ----------
    command: :class:`Command`
        The command that failed to be converted.
    """

    def __init__(self, command: commands.Command, msg: Optional[str] = None) -> None:
        self.command = command
        super().__init__(msg or f"{command.qualified_name} failed to converted to an application command.")
