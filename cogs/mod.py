import discord
from discord.ext import commands, tasks

from botpersistent import Module
from bot import admin_id

class Mod(Module):
    def __init__(self, client):
        super().__init__(client)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.message_id == 778747770063552514:
            role = discord.utils.get(self.client.guild.roles, name="Apprenti")
            await payload.member.add_roles(role)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        channel = discord.utils.get(member.guild.channels, name="logs")
        await channel.send(f"{member.name} ({member.id}) est parti")

    @commands.command()
    @commands.has_any_role(admin_id)
    async def clear(self, ctx, count: int):
        if count > 100:
            return
        await ctx.channel.purge(limit=count)
    
    @commands.command()
    @commands.has_any_role(admin_id)
    async def img(self, ctx):
        with open('image.png', 'rb') as f:
            await self.client.user.edit(avatar=f.read())
        print("Sucessfully updated the bot's profile picture")


def setup(client):
    client.add_cog(Mod(client))
