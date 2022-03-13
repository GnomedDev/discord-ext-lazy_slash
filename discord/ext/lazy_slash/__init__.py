from typing import Iterable, Optional, Type

import discord
from discord.ext import commands

from .from_slash import process_slash_commands
from .to_slash import create_slash_commands
from .context import SlashContext
from .patches import Option  # also has side effects

__all__ = ("SlashBot", "SlashContext", "process_slash_commands", "create_slash_commands", "Option")


class SlashBot(commands.Bot):
    def __init__(self, *args, auto_upload: bool, slash_command_guilds: Optional[Iterable[int]] = None, **kwargs):
        self.auto_upload = auto_upload
        self.slash_command_guilds = slash_command_guilds

        super().__init__(*args, **kwargs)

    on_interaction = process_slash_commands

    async def setup_hook(self):
        await super().setup_hook()

        if not self.auto_upload:
            return None

        if self.slash_command_guilds is None:
            await create_slash_commands(self, upload_as_global=self.commands)
        else:
            for guild in self.slash_command_guilds:
                await create_slash_commands(self, upload_as_guild={guild: list(self.all_commands.values())})

    async def get_context(
        self, message: discord.Message, cls: Type[commands.Context] = SlashContext
    ) -> commands.Context:
        return await super().get_context(message, cls=cls)
