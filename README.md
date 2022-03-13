# discord-ext-lazy_slash

A discord.py slash command extension based on the slash command implementation in [enhanced discord.py](https://github.com/idevision/enhanced-discord.py).

This is not well written or fast code at all, but it is well tested, works, and is easy.

# Setup
1. Replace `commands.Bot(...)` with `lazy_slash.SlashBot(auto_upload=True, ...)`
2. You have slash commands.

# Docs
## ``SlashBot``
commands.Bot with a premade ``on_interaction``, ``setup_hook``, and ``get_context``, recommended to use this.

## ``SlashContext``
commands.Context but with helpers for ``send`` and ``reply`` to use interaction methods + the async ``defer`` function which takes:

trigger_typing: ``bool`` = True
- Indicates whether to trigger typing in a prefix command.

ephemeral: ``bool`` = False
- Indicates whether the deferred message will eventually be ephemeral in a slash command.

## ``process_slash_commands``
Processes an interaction into a message object and invokes it:

bot: ``commands.Bot``
- The bot object to invoke with

interaction: ``discord.Interaction``
- The slash command interaction object to invoke

## ``create_slash_commands``
Processes the given command objects into slash commands and uploads them:
bot: ``commands.Bot``
- The bot object to convert with

upload_as_global: ``Iterable[commands.Command]`` = ``[]``
- The slash commands to upload globally, **takes up to an hour**

upload_as_guild: ``Dict[discord.Object, List[commands.Command]]`` = ``{}``
- The slash commands to upload to specific guilds, works instantly, **good for testing or small bots**

## ``Option``
A special 'converter' to apply a description to slash command options.

description: `str`
- The description to show on slash command invokes

default: `Any` = ``inspect._empty``
- The default parameter that would be there otherwise

```py
@bot.command()
async def ban(ctx,
    member: discord.Member, *,
    reason: str = commands.Option('no reason', description='the reason to ban this member')
):
    await member.ban(reason=reason)
```
