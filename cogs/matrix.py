import asyncio
import aiohttp
import logging
import re
import traceback

import discord
from discord.ext import commands
from discord.ext.commands import Group

from botpersistent import Module


class Matrix(Module):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bridged_ids = {"!VztthSUDLToJgvJGdx:iiens.net": 772061551195979797}

    @commands.Cog.listener()
    async def on_ready(self):
        print("Matrix bridge started")
        loop = asyncio.get_running_loop()
        loop.create_task(self.log_matrix())

    async def log_matrix(self):
        proxies = {}
        logging.basicConfig(level=logging.INFO)

        ACCESS_TOKEN = self.data["matrix"]
        HS_URL = self.data["hs_url"]

        async with aiohttp.ClientSession() as session:
            while True:
                logging.info("Syncing")
                try:
                    if self.data["next_batch"]:
                        params = {"access_token": ACCESS_TOKEN, "since": self.data["next_batch"], "timeout": 10000}
                    else:
                        params = {"access_token": ACCESS_TOKEN, "timeout": 10000}
                    async with session.get(HS_URL + "/_matrix/client/r0/sync", headers={"Content-Type": "application/json"},
                                           params=params) as response:
                        sync = await response.json()
                        self.data["next_batch"] = sync["next_batch"]
                        for room_id, room in sync["rooms"]["join"].items():
                            for event in room["timeline"]["events"]:
                                if event["type"] == "m.room.message":
                                    print(event['content']['body'])
                                    await self.process(event, room_id)
                except Exception:
                    traceback.print_exc()

    async def process(self, event, room_id):
        matrix_room = self.bridged_ids.get(room_id)
        if not matrix_room:
            return

        user = Member(event['sender'], event['sender'])
        if user.id.startswith("@_discord_"): return

        message = Message(event['content']['body'], user)
        channel = self.client.get_channel(matrix_room)
        ctx = Context(self.client, self.client.guild, channel, user)

        for method in self.client.extra_events["on_message"]:
            await method(message)

        if not message.content.startswith(self.client.command_prefix):
            return

        command, args = self.com(self.client.commands, message.content[1:].split())
        if command and not command.checks:
            await command(ctx, *args)

    def com(self, space, args):
        e = [c for c in space if c.name == args[0]]
        if not e:
            return None
        e = e[0]
        args.pop(0)
        if args and isinstance(e, Group):
            return self.com(e.commands, args)
        return e, args


def setup(client):
    client.add_cog(Matrix(client))


class Context:
    def __init__(self, client, guild, channel, author):
        self.bot = client
        self.guild = guild
        self.channel = channel
        self.author = author
        self.invoked_subcommand = None

    async def send(self, *args, **kwargs):
        await self.channel.send(*args, **kwargs)

class Member:
    def __init__(self, _id, name):
        self.bot = False
        self.id = _id
        self.display_name = name

    @staticmethod
    async def convert(ctx, arg):
        if isinstance(arg, Member):
            return arg

        # Discord
        if len(arg) > 5 and arg[-5] == '#':
            username, _, discriminator = arg.rpartition('#')
            members = await ctx.guild.query_members(username, limit=100)
            res = discord.utils.get(members, name=username, discriminator=discriminator)
            return Member(res.id, res.display_name)

        # Matrix
        cursor = ctx.bot.mydb.cursor()
        cursor.execute("SELECT * FROM users "
                       "WHERE id = ? ",
                       (arg,))
        id = cursor.fetchone()[0]
        if id:
            return Member(id, id)

        raise Exception


class Message:
    def __init__(self, content, author):
        self.bot = False
        self.content = content
        self.author = author