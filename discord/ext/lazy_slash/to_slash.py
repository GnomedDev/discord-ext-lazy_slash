from __future__ import annotations

import inspect
from collections import defaultdict
from operator import itemgetter
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Literal, Optional, Union, cast

import discord
from discord.ext import commands

from . import errors

if TYPE_CHECKING:
    from discord.types.interactions import ApplicationCommandInteractionDataOption


REVERSED_CONVERTER_MAPPING = {v: k for k, v in commands.converter.CONVERTER_MAPPING.items()}
APPLICATION_OPTION_TYPE_LOOKUP = {
    str: 3,
    bool: 5,
    int: 4,
    (
        discord.Member,
        discord.User,
    ): 6,  # Preferably discord.abc.User, but 'Protocols with non-method members don't support issubclass()'
    (discord.abc.GuildChannel, discord.Thread): 7,
    discord.Role: 8,
    float: 10,
}
APPLICATION_OPTION_CHANNEL_TYPES = {
    discord.VoiceChannel: [2],
    discord.TextChannel: [0, 5, 6],
    discord.CategoryChannel: [4],
    discord.Thread: [10, 11, 12],
    discord.StageChannel: [13],
}


def _param_to_options(
    command: commands.Command,
    name: str,
    annotation: Any,
    required: bool,
    varadic: bool,
) -> List[Optional[ApplicationCommandInteractionDataOption]]:

    description = getattr(command, "option_descriptions", {}).get(name) or "no description"
    origin = getattr(annotation, "__origin__", None)

    if inspect.isclass(annotation) and issubclass(annotation, commands.FlagConverter):
        return [
            param
            for name, flag in annotation.get_flags().items()
            for param in _param_to_options(
                command,
                name,
                flag.annotation,
                required=flag.required,
                varadic=flag.annotation is tuple,
            )
        ]

    if varadic:
        annotation = str
        origin = None

    annotation = cast(Any, annotation)
    if not required and origin is Union and annotation.__args__[-1] is type(None):
        # Unpack Optional[T] (Union[T, None]) into just T
        annotation = annotation.__args__[0]
        origin = getattr(annotation, "__origin__", None)

    option: Dict[str, Any] = {
        "type": 3,
        "name": name,
        "required": required,
        "description": description,
    }

    if origin is None:
        if not inspect.isclass(annotation):
            annotation = type(annotation)

        if issubclass(annotation, commands.Converter):
            # If this is a converter, we want to check if it is a native
            # one, in which we can get the original type, eg, (MemberConverter -> Member)
            annotation = REVERSED_CONVERTER_MAPPING.get(annotation, annotation)

        for python_type, discord_type in APPLICATION_OPTION_TYPE_LOOKUP.items():
            if issubclass(annotation, python_type):
                option["type"] = discord_type
                # Set channel types
                if discord_type == 7:
                    option["channel_types"] = APPLICATION_OPTION_CHANNEL_TYPES[annotation]  # type: ignore
                break

    elif origin is Union:
        if annotation in {Union[discord.Member, discord.Role], Union[commands.MemberConverter, commands.RoleConverter]}:
            option["type"] = 9

        elif all([arg in APPLICATION_OPTION_CHANNEL_TYPES for arg in annotation.__args__]):
            option["type"] = 7
            option["channel_types"] = [
                discord_value for arg in annotation.__args__ for discord_value in APPLICATION_OPTION_CHANNEL_TYPES[arg]
            ]

    elif origin is Literal:
        literal_values = annotation.__args__
        python_type = type(literal_values[0])
        if (
            all(type(value) == python_type for value in literal_values)
            and python_type in APPLICATION_OPTION_TYPE_LOOKUP.keys()
        ):

            option["type"] = APPLICATION_OPTION_TYPE_LOOKUP[python_type]
            option["choices"] = [
                {"name": literal_value, "value": literal_value} for literal_value in annotation.__args__
            ]

    return [option]  # type: ignore


def to_application_group(command: commands.Group, nested: int = 0) -> Optional[dict]:
    if nested == 2:
        raise errors.ApplicationCommandRegistrationError(command, f"{command.qualified_name} is too deeply nested!")

    return {
        "name": command.name,
        "type": int(not (nested - 1)) + 1,
        "description": command.short_doc or "no description",
        "options": [
            to_application_command(command, nested=nested + 1) for cmd in sorted(command.commands, key=lambda x: x.name)
        ],
    }


def to_application_command(command: commands.Command, nested: int = 0) -> Optional[dict]:
    if nested == 3:
        raise errors.ApplicationCommandRegistrationError(command, f"{command.qualified_name} is too deeply nested!")

    payload = {"name": command.name, "description": command.short_doc or "no description", "options": []}
    if nested != 0:
        payload["type"] = 1

    for name, param in command.clean_params.items():
        options = _param_to_options(
            command,
            name,
            param.annotation if param.annotation is not param.empty else str,
            varadic=param.kind == param.KEYWORD_ONLY or isinstance(param.annotation, commands.Greedy),
            required=(param.default is param.empty and not command._is_typing_optional(param.annotation))
            or param.kind == param.VAR_POSITIONAL,
        )
        if options is not None:
            payload["options"].extend(option for option in options if option is not None)

    # Now we have all options, make sure required is before optional.
    payload["options"] = sorted(payload["options"], key=itemgetter("required"), reverse=True)
    return payload


async def create_slash_commands(
    bot: commands.Bot,
    *,
    upload_as_global: Iterable[commands.Command] = [],
    upload_as_guild: Dict[int, List[commands.Command]] = {},
):
    ext_commands: defaultdict[Optional[int], List[commands.Command]] = defaultdict(list)
    ext_commands[None].extend(upload_as_global)
    for (g, c) in upload_as_guild.items():
        ext_commands[g].extend(c)

    slash_commands: defaultdict[Optional[int], List[dict]] = defaultdict(list)
    for guild_id, up_commands in ext_commands.items():
        for command in up_commands:
            if command.hidden:
                continue

            try:
                if command.hidden:
                    return None

                slash_commands[guild_id].append(to_application_command(command))
            except Exception as error:
                raise RuntimeError(f"Encountered error while uploading command: {command.qualified_name}") from error

    application_id = bot.application_id or (await bot.application_info()).id
    await bot.http.bulk_upsert_global_commands(
        payload=slash_commands.pop(None, None),
        application_id=application_id,
    )

    if upload_as_guild:
        for guild, command in slash_commands.items():
            assert guild is not None
            await bot.http.bulk_upsert_guild_commands(
                guild_id=guild,
                payload=command,
                application_id=application_id,
            )
