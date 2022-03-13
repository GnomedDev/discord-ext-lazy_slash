from __future__ import annotations

import inspect
from collections import defaultdict
from typing import Any

import discord
from discord.ext import commands
from discord.utils import MISSING


class Option:  # type: ignore
    """A special 'converter' to apply a description to slash command options.

    For example in the following code:

    .. code-block:: python3

        @bot.command()
        async def ban(ctx,
            member: discord.Member, *,
            reason: str = commands.Option('no reason', description='the reason to ban this member')
        ):
            await member.ban(reason=reason)

    The description would be ``the reason to ban this member`` and the default would be ``no reason``

    Attributes
    ------------
    default: Optional[Any]
        The default for this option, overwrites Option during parsing.
    description: :class:`str`
        The description for this option, is unpacked to :attr:`.Command.option_descriptions`
    """

    __slots__ = (
        "default",
        "description",
    )

    def __init__(self, default: Any = inspect.Parameter.empty, *, description: str) -> None:
        self.description = description
        self.default = default


Option: Any


@commands.Command.callback.setter
def callback(self, function):
    super(self).callback = function

    signature = inspect.signature(function)
    self.option_descriptions = defaultdict(lambda: "no description")

    for name, parameter in signature.parameters.items():
        if isinstance(parameter.default, Option):  # type: ignore
            option = parameter.default
            parameter = parameter.replace(default=option.default)
            if option.name is not MISSING:
                name = option.name
                parameter.replace(name=name)

            self.option_descriptions[name] = option.description


# Need to ignore CommandNotFound because otherwise on_interaction is never called
original_transform = commands.Command.transform
original_call = discord.app_commands.CommandTree.call


async def transform(self, ctx: commands.Context, param: inspect.Parameter):
    if hasattr(ctx, "_ignored_params") and param in ctx._ignored_params:  # type: ignore
        # in a slash command, we need a way to mark a param as default so ctx._ignored_params is used
        return param.default if param.default is not param.empty else None

    return await original_transform(self, ctx, param)


async def call(*args, **kwargs):
    try:
        return await original_call(*args, **kwargs)
    except discord.app_commands.CommandNotFound:
        pass


commands.Command.transform = transform
discord.app_commands.CommandTree.call = call
