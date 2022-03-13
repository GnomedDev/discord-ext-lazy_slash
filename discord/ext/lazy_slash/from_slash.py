from __future__ import annotations

import functools
import inspect
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, Union, cast

import discord
from discord.ext import commands
from discord.ext.commands.view import _quotes as supported_quotes

if TYPE_CHECKING:
    from discord.types.interactions import ApplicationCommandInteractionData, ApplicationCommandInteractionDataOption


class _FakeSlashMessage(discord.PartialMessage):
    activity = application = edited_at = reference = webhook_id = None
    attachments = components = reactions = stickers = []
    tts = False

    raw_mentions = discord.Message.raw_mentions
    clean_content = discord.Message.clean_content
    channel_mentions = discord.Message.channel_mentions
    raw_role_mentions = discord.Message.raw_role_mentions
    raw_channel_mentions = discord.Message.raw_channel_mentions

    author: Union[discord.User, discord.Member]

    @classmethod
    def from_interaction(
        cls, interaction: discord.Interaction, channel: Union[discord.TextChannel, discord.DMChannel, discord.Thread]
    ):
        self = cls(channel=channel, id=interaction.id)
        assert interaction.user is not None
        self.author = interaction.user

        return self

    @functools.cached_property
    def mentions(self) -> List[Union[discord.Member, discord.User]]:
        client = self._state._get_client()
        if self.guild:
            ensure_user = lambda id: self.guild.get_member(id) or client.get_user(id)  # type: ignore
        else:
            ensure_user = client.get_user

        return discord.utils._unique(filter(None, map(ensure_user, self.raw_mentions)))  # type: ignore

    @functools.cached_property
    def role_mentions(self) -> List[discord.Role]:
        if self.guild is None:
            return []
        return discord.utils._unique(filter(None, map(self.guild.get_role, self.raw_role_mentions)))  # type: ignore


def _quote_string_safe(string: str) -> str:
    for open, close in supported_quotes.items():
        if open not in string and close not in string:
            return f"{open}{string}{close}"

    raise commands.UnexpectedQuoteError(string)


def _unwrap_slash_groups(
    data: ApplicationCommandInteractionData,
) -> Tuple[str, Dict[str, ApplicationCommandInteractionDataOption]]:
    command_name = data["name"]
    command_options: Any = data.get("options") or []
    while True:
        try:
            option = next(o for o in command_options if o["type"] in {1, 2})
        except StopIteration:
            return command_name, {o["name"]: o for o in command_options}
        else:
            command_name += f' {option["name"]}'
            command_options = option.get("options") or []


async def process_slash_commands(bot: commands.Bot, interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.application_command:
        return

    if TYPE_CHECKING:
        interaction.data = cast(ApplicationCommandInteractionData, interaction.data)

    command_name, command_options = _unwrap_slash_groups(interaction.data)
    command = bot.get_command(command_name)
    if command is None:
        raise commands.CommandNotFound(f'Command "{command_name}" is not found')

    # Ensure the interaction channel is usable
    channel = interaction.channel
    if channel is None or isinstance(channel, discord.PartialMessageable):
        if interaction.guild is None:
            assert interaction.user is not None
            channel = await interaction.user.create_dm()
        elif interaction.channel_id is not None:
            channel = await interaction.guild.fetch_channel(interaction.channel_id)
        else:
            return  # cannot do anything without stable channel

    # Make our fake message so we can pass it to ext.commands
    message: discord.Message = _FakeSlashMessage.from_interaction(interaction, channel)  # type: ignore
    message.content = command_name

    # Add arguments to fake message content, in the right order
    ignored_params = []
    for name, param in command.clean_params.items():
        if inspect.isclass(param.annotation) and issubclass(param.annotation, commands.FlagConverter):
            for name, flag in param.annotation.get_flags().items():
                option = command_options.get(name)

                if option is None:
                    if flag.required:
                        raise commands.MissingRequiredFlag(flag)
                else:
                    prefix = param.annotation.__commands_flag_prefix__
                    delimiter = param.annotation.__commands_flag_delimiter__
                    message.content += f" {prefix}{name}{delimiter}{option['value']}"  # type: ignore
            continue

        option = command_options.get(name)
        if option is None:
            if param.default is param.empty and not command._is_typing_optional(param.annotation):
                raise commands.MissingRequiredArgument(param)
            elif param.annotation is None or param.annotation == str:
                message.content += f" { _quote_string_safe('')}"
            else:
                ignored_params.append(param)  # type: ignore
        elif (
            option["type"] == 3
            and not isinstance(param.annotation, commands.Greedy)
            and param.kind in {param.POSITIONAL_OR_KEYWORD, param.POSITIONAL_ONLY}
        ):
            # String with space in without "consume rest"
            message.content += f" {_quote_string_safe(option['value'])}"
        else:
            message.content += f' {option.get("value", "")}'

    prefix = await bot.get_prefix(message)
    if isinstance(prefix, list):
        prefix = prefix[0]

    message.content = f"{prefix}{message.content}"

    ctx = await bot.get_context(message)
    ctx._ignored_params = ignored_params  # type: ignore
    ctx.interaction = interaction  # type: ignore
    await bot.invoke(ctx)
