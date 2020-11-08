import os

import sqlite3
import discord
from discord.ext import commands

from botpersistent import BotPersistent


class ChatoBot(BotPersistent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild = 0
        self.embedColor = 0x0000ff
        self.mydb = sqlite3.connect('circe.db')
        self.mydb.set_trace_callback(print)

        for filename in self.data["load"]:
            self.load_extension(f"cogs.{filename}")
            print(f"loaded {filename}")

    async def on_ready(self):
        print('Logged in as')
        print(self.user.name)
        print(self.user.id)
        print('------')
        self.guild = self.get_guild(self.data["guild_id"])

    async def on_message(self, message):
        await self.process_commands(message)

    @staticmethod
    def cogs_list():
        return [filename for filename in os.listdir("./cogs") if filename.endswith(".py")]


client = ChatoBot(command_prefix='!')
client.command_prefix = client.data["prefix"]

@client.command()
@commands.has_any_role("Circé")
async def load(ctx, extension):
    client.load_extension(f"cogs.{extension}")
    client.data["load"].append(extension)
    print(f"loaded {extension}")


@client.command()
@commands.has_any_role("Circé")
async def unload(ctx, extension):
    client.unload_extension(f"cogs.{extension}")
    client.data["load"].pop(extension)
    print(f"unloaded {extension}")


@client.command()
@commands.has_any_role("Circé")
async def shutdown(ctx):
    client.save()
    for filename in client.data["load"]:
        client.unload_extension(f"cogs.{filename}")
        print(f"unloaded {filename}")
    await client.close()


@client.command()
@commands.has_any_role("Circé")
async def reload(ctx):
    client.save()
    await client.logout()


@client.command()
@commands.has_any_role("Circé")
async def prefix(ctx, prefix=None):
    if prefix:
        client.command_prefix = prefix
        await ctx.send(f"prefix set to {prefix}")
    else:
        await ctx.send(client.command_prefix)

client.save()
client.run(client.data["token"])
