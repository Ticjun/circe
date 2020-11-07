import typing
from discord.ext import commands
from botpersistent import Module
import discord
import random


class Tarot(Module):
    def __init__(self, client):
        super().__init__(client)
        self.n_decks = 2
        self.n_cards = 22

    @commands.Cog.listener()
    async def on_ready(self):
        self.redeem_channel = self.client.get_channel(774622426080083999)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            cursor = self.client.mydb.cursor()
            cursor.execute("SELECT * FROM users "
                           "WHERE id = ? ",
                           (message.author.id,))
            result = cursor.fetchone()

            if result is None:
                print("user not in db")
                cursor.execute("INSERT INTO users VALUES(?)",
                               (message.author.id,))
                print(f"inserted user {message.author.name}")
            self.client.mydb.commit()

    @commands.command()
    @commands.has_any_role("Circé")
    async def fill(self, ctx):
        cursor = self.client.mydb.cursor()
        cards = [(deck, card) for deck in range(1, self.n_decks+1) for card in range(0, self.n_cards)]
        random.shuffle(cards)
        for card in cards:
            cursor.execute("INSERT INTO cards VALUES(?, ?, 0)",
                           (*card, ))
        self.client.mydb.commit()
        ctx.send("Cartes ajoutées")

    @commands.command()
    @commands.has_any_role("Circé")
    async def give(self, ctx, card_n, member: discord.Member):
        if card_n == "rand":
            cursor = self.client.mydb.cursor()
            cursor.execute("SELECT deck_n, card_n FROM cards "
                           "WHERE user_id = 0")
        else:
            cursor = self.client.mydb.cursor()
            cursor.execute("SELECT deck_n, card_n FROM cards "
                           "WHERE card_n = ? AND user_id = 0",
                           (card_n,))
        result = cursor.fetchone()
        if result:
            cursor.execute("UPDATE cards SET user_id = ? "
                           "WHERE deck_n = ? AND card_n = ?",
                           (member.id, *result))
            self.client.mydb.commit()
            await ctx.send(f"{member.display_name} a obtenue la carte {result[1]}")
        else:
            await ctx.send("Carte introuvable !")

    @commands.command()
    async def redeem(self, ctx, code):
        cursor = self.client.mydb.cursor()
        cursor.execute("SELECT card_n FROM codes "
                       "WHERE code = ? AND used = 0 ",
                       (code,))
        result = cursor.fetchone()
        if result:
            cursor.execute("UPDATE codes SET used = 1 "
                           "WHERE code = ?",
                           (code, ))
            self.client.mydb.commit()
            await ctx.send("Code correct")
            await ctx.invoke(self.give, result[0], ctx.author)

    @commands.command()
    async def inv(self, ctx, member: typing.Optional[discord.Member]):
        if not member:
            msg = "Vos cartes : \n"
            member = ctx.author
        else:
            msg = msg = f"Cartes de {member.display_name}: \n"
        cursor = self.client.mydb.cursor()

        cursor.execute("SELECT prefix, name FROM cards_info")
        cards_info = cursor.fetchall()
        cursor.execute("SELECT card_n, COUNT(*) FROM cards "
                       "WHERE user_id = ? "
                       "GROUP BY card_n ",
                       (member.id,))
        result = cursor.fetchall()
        result = dict(result)

        msg +="```diff\n"
        for i, (prefix, name) in enumerate(cards_info):
            count = result.get(i+1)
            if count:
                msg += f"+ {prefix:<8} {name:<20} x{count:<10}\n"
            else:
                msg += f"- {prefix:<8} {name:<20} x0\n"
        msg += "```"
        await ctx.send(msg)

    @commands.command()
    async def show(self, ctx, number: int):
        cursor = self.client.mydb.cursor()
        cursor.execute("SELECT url, unlocked FROM cards_info "
                       "WHERE n = ? ",
                       (number,))
        url, unlocked = cursor.fetchone()
        if unlocked:
            await ctx.send(url)
        else:
            await ctx.send("Cette carte n'est pas encore disponible")

    @commands.command()
    @commands.has_any_role("Circé")
    async def unlock(self, ctx, number: int):
        cursor = self.client.mydb.cursor()
        cursor.execute("UPDATE cards_info SET unlocked = 1 "
                       "WHERE n = ?",
                       (number,))
        self.client.mydb.commit()
        await ctx.send(f"Carte {number} débloquée")


def setup(client):
    client.add_cog(Tarot(client))