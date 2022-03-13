import asyncio
from typing import Any, Literal, Optional, Union, overload

import discord
from discord.ext import commands


class SlashContext(commands.Context):
    interaction: discord.Interaction

    @overload
    async def send(
        self,
        content: Optional[str] = None,
        return_message: Literal[False] = False,
        ephemeral: bool = False,
        **kwargs: Any,
    ) -> Optional[Union[discord.Message, discord.WebhookMessage]]:
        ...

    @overload
    async def send(
        self,
        content: Optional[str] = None,
        return_message: Literal[True] = True,
        ephemeral: bool = False,
        **kwargs: Any,
    ) -> Union[discord.Message, discord.WebhookMessage]:
        ...

    async def send(
        self, content: Optional[str] = None, return_message: bool = True, ephemeral: bool = False, **kwargs: Any
    ) -> Optional[Union[discord.Message, discord.WebhookMessage]]:
        """
        |coro|

        A shortcut method to :meth:`.abc.Messageable.send` with interaction helpers.

        This function takes all the parameters of :meth:`.abc.Messageable.send` plus the following:

        Parameters
        ------------
        return_message: :class:`bool`
            Ignored if not in a slash command context.
            If this is set to False more native interaction methods will be used.
        ephemeral: :class:`bool`
            Ignored if not in a slash command context.
            Indicates if the message should only be visible to the user who started the interaction.
            If a view is sent with an ephemeral message and it has no timeout set then the timeout
            is set to 15 minutes.

        Returns
        --------
        Optional[Union[:class:`.Message`, :class:`.WebhookMessage`]]
            In a slash command context, the message that was sent if return_message is True.

            In a normal context, it always returns a :class:`.Message`
        """

        if hasattr(self, "_typing_task"):
            self._typing_task.cancel()
            del self._typing_task

        if self.interaction is None:
            return await super().send(content, **kwargs)

        # Remove unsupported arguments from kwargs
        kwargs.pop("nonce", None)
        kwargs.pop("stickers", None)
        kwargs.pop("reference", None)
        kwargs.pop("mention_author", None)

        if not (return_message or self.interaction.response.is_done()):
            send = self.interaction.response.send_message
        else:
            # We have to defer in order to use the followup webhook
            if not self.interaction.response.is_done():
                await self.interaction.response.defer(ephemeral=ephemeral)

            send = self.interaction.followup.send

        return await send(content, ephemeral=ephemeral, **kwargs)  # type: ignore

    @overload
    async def reply(
        self, content: Optional[str] = None, return_message: Literal[False] = False, **kwargs: Any
    ) -> Optional[Union[discord.Message, discord.WebhookMessage]]:
        ...

    @overload
    async def reply(
        self, content: Optional[str] = None, return_message: Literal[True] = True, **kwargs: Any
    ) -> Union[discord.Message, discord.WebhookMessage]:
        ...

    @discord.utils.copy_doc(discord.Message.reply)
    async def reply(
        self, content: Optional[str] = None, return_message: bool = True, **kwargs: Any
    ) -> Optional[Union[discord.Message, discord.WebhookMessage]]:
        return await self.send(content, return_message=return_message, reference=self.message, **kwargs)  # type: ignore

    async def defer(self, *, ephemeral: bool = False, trigger_typing: bool = True) -> None:
        """|coro|

        Defers the Slash Command interaction if ran in a slash command **or**

        Loops triggering ``Bot is typing`` in the channel if run in a message command.

        Parameters
        ------------
        trigger_typing: :class:`bool`
            Indicates whether to trigger typing in a message command.
        ephemeral: :class:`bool`
            Indicates whether the deferred message will eventually be ephemeral in a slash command.
        """

        if self.interaction is None:
            if not hasattr(self, "_typing_task") and trigger_typing:

                async def typing_task():
                    while True:
                        await self.trigger_typing()
                        await asyncio.sleep(10)

                self._typing_task = self.bot.loop.create_task(typing_task())
        else:
            await self.interaction.response.defer(ephemeral=ephemeral)
