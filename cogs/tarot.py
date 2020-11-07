import typing
from discord.ext import commands
from botpersistent import Module
import discord
import random

card_names = [
"O-Le Mat",
"I-Le Bateleur",
"II-La Papesse",
"III-L'Impératrice",
"IIII-L'Empereur",
"V-Le Pape",
"VI-L'Amoureux",
"VII-Le Chariot",
"VIII-La Justice",
"VIIII-L'Ermite",
"X-La Roue de Fortune",
"XI-La Force",
"XII-Le Pendu",
"XIII-La Mort",
"XIIII-Tempérance",
"XV-Le Diable",
"XVI-La Maison Dieu",
"XVII-L'Étoile",
"XVIII-La Lune",
"XVIIII-Le Soleil",
"XX-Le Jugement",
"XXI-Le Monde"
]
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
        cards = [(deck, card) for deck in range(1, self.n_decks+1) for card in range(1, self.n_cards+1)]
        random.shuffle(cards)
        for card in cards:
            cursor.execute("INSERT INTO cards VALUES(?, ?, 0)",
                           (*card, ))
        self.client.mydb.commit()

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
        cursor.execute("SELECT card_n, COUNT(*) FROM cards "
                       "WHERE user_id = ? "
                       "GROUP BY card_n ",
                       (member.id,))
        result = cursor.fetchall()
        result = dict(result)

        msg +="```diff\n"
        for i in range(self.n_cards):
            count = result.get(i+1)
            if count:
                msg+=f"+ {card_names[i]} x{count}\n"
            else:
                msg += f"- {card_names[i]} x0\n"
        msg += "```"
        await ctx.send(msg)


def setup(client):
    client.add_cog(Tarot(client))
