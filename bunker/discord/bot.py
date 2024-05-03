import asyncio
import logging
import os
from pathlib import Path

import discord
from discord.ext import commands

from bunker.discord.utils import handle_error
from bunker.constants import DISCORD_COGS_PATH, DISCORD_GUILD_ID

__all__ = (
    "bot",
)

async def load_all_cogs():
    cog_path_template = DISCORD_COGS_PATH.as_posix().replace("/", ".") + ".{}"
    for cog_name in os.listdir(DISCORD_COGS_PATH):
        if cog_name.endswith(".py"):
            try:
                cog_path = cog_path_template.format(os.path.splitext(cog_name)[0])
                await bot.load_extension(cog_path)
            except:
                logging.exception(f"Cog {cog_name} cannot be loaded")
                pass
    logging.info('Loaded all cogs')

async def sync_commands():
    try:
        await asyncio.wait_for(bot.tree.sync(guild=discord.Object(DISCORD_GUILD_ID)), timeout=5)
        await asyncio.wait_for(bot.tree.sync(), timeout=5)
        logging.info('Synced app commands')
    except asyncio.TimeoutError:
        logging.warn("Didn't sync app commands. This was likely last done recently, resulting in rate limits.")


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.remove_command('help')
        self.allowed_mentions = discord.AllowedMentions.none()
    
    async def setup_hook(self) -> None:
        await load_all_cogs()
        await sync_commands()
        # TODO: this is lazy and ugly
        from bunker.discord.views.enroll import EnrollView, EnrollAcceptView
        from bunker.discord.views.submit_report import GetSubmissionURLView
        self.add_view(EnrollView())
        self.add_view(EnrollAcceptView())
        self.add_view(GetSubmissionURLView())

    @property
    def primary_guild(self):
        guild = self.get_guild(DISCORD_GUILD_ID)
        if guild is None:
            raise RuntimeError("Guild not found")
        return guild
    
    async def get_or_fetch_user(self, user_id: int):
        guild = self.primary_guild
        member = guild.get_member(user_id)
        if member:
            return member
        else:
            return await guild.fetch_member(user_id)
        
    def get_partial_message(self, channel_id: int, message_id: int):
        return self.get_partial_messageable(channel_id).get_partial_message(message_id)

    async def delete_message(self, channel_id: int, message_id: int):
        message = self.get_partial_messageable()
        await message.delete()

def command_prefix(bot: Bot, message: discord.Message):
    return bot.user.mention + " "

bot = Bot(
    intents=discord.Intents.default(),
    command_prefix=command_prefix,
    case_insensitive=True
)

@bot.tree.error
async def on_interaction_error(interaction: discord.Interaction, error: Exception):
    await handle_error(interaction, error)

@bot.command()
@commands.is_owner()
async def reload(ctx: commands.Context, cog_name: str = None):
    async def reload_cog(ctx: commands.Context, cog_name):
        try:
            await bot.reload_extension(f"cogs.{cog_name}")
            await ctx.send(f"Reloaded {cog_name}")
        except Exception as e:
            await ctx.send(f"Couldn't reload {cog_name}, " + str(e))

    if not cog_name:
        for cog_name in os.listdir(Path("./cogs")):
            if cog_name.endswith(".py"):
                cog_name = cog_name.replace(".py", "")
                await reload_cog(ctx, cog_name)
    else:
        if os.path.exists(Path(f"./cogs/{cog_name}.py")):
            await reload_cog(ctx, cog_name)
        else:
            await ctx.send(f"{cog_name} doesn't exist")

