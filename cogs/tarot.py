from discord.ext import commands
from botpersistent import Module
from bot import admin_id
from cogs.matrix import Member
import discord
import random
import asyncio
from dataclasses import dataclass


class Side:
    def __init__(self, member):
        self.member = member
        self.trade = {}
        self.ok = False


@dataclass
class Card:
    n: int
    prefix: str
    name: str
    url: str
    desc: str
    color: str
    role_id: int
    unlocked: bool


class Trade:
    def __init__(self, cog, left, right):
        self.cog = cog
        self.left_side = Side(left)
        self.right_side = Side(right)
        self.right_side.ok = True

    def get_side(self, is_left):
        if is_left:
            me = self.left_side
        else:
            me = self.right_side
        return me

    async def add(self, ctx, number, is_left):
        self.left_side.ok, self.right_side.ok = False, False
        side = self.get_side(is_left)
        n_card = self.cog.inv_dict(side.member).get(number)
        if not n_card:
            await ctx.send("Vous ne possédez pas cette carte")
        elif n_card < (side.trade.get(number) or 0) + 1:
            await ctx.send("Vous ne possédez pas suffisament de cartes pour effectuer cet échange")
        else:
            side.trade[number] = 1 + (side.trade.get(number) or 0)
            await self.update(ctx)

    async def rem(self, ctx, number, is_left):
        self.left_side.ok, self.right_side.ok = False, False
        side = self.get_side(is_left)
        n = side.trade.get(number)
        if n:
            side.trade[number] -= 1
            if n == 1:
                side.trade.pop(number)
            await self.update(ctx)
        else:
            await ctx.send("Opération impossible")

    async def accept(self, ctx, is_left):
        side = self.get_side(is_left)
        side.ok = True
        if self.right_side.ok and self.left_side.ok:
            await ctx.send("Les deux participants se sont mis d'accord")
            self.execute()
            await ctx.send("Echange terminé")
            return
        await self.update(ctx)

    async def update(self, ctx):
        embed = discord.Embed(title="Echange", color=0x000000)
        embed.add_field(name=self.left_side.member.display_name, value=self.stringify(self.left_side), inline=True)
        embed.add_field(name=self.right_side.member.display_name, value=self.stringify(self.right_side), inline=True)
        await ctx.send(embed=embed)

    def stringify(self, side):
        str = ""
        card_infos = self.cog.cards()
        for card_n, count in list(side.trade.items()):
            str += f"{card_infos[card_n].prefix}-{card_infos[card_n].name} x{count}\n"
        if not str: str += "Rien"
        if side.ok: str = "✅\n" + str
        else: str = "❎\n" + str
        return str

    def execute(self):
        cursor = self.cog.bot.mydb.cursor()
        query = ("UPDATE cards SET user_id = ? "
                 "WHERE (deck_n, card_n) IN ( "
                 "SELECT deck_n, card_n FROM cards "
                 "WHERE user_id = ? AND card_n = ? "
                 "LIMIT 1 )")
        for card_n, count in list(self.left_side.trade.items()):
            for _ in range(count):
                cursor.execute(query, (-1, self.left_side.member.id, card_n))
        for card_n, count in list(self.right_side.trade.items()):
            for _ in range(count):
                cursor.execute(query, (self.left_side.member.id, self.right_side.member.id, card_n))
        for card_n, count in list(self.left_side.trade.items()):
            for _ in range(count):
                cursor.execute(query, (self.right_side.member.id, -1, card_n))
        self.cog.bot.mydb.commit()


class Tarot(Module):
    def __init__(self, client):
        super().__init__(client)
        self.n_decks = 2
        self.n_cards = 22
        self.trades = []

    @commands.command()
    @commands.has_any_role(admin_id)
    async def random_spawn(self, ctx):
        while True:
            time = random.uniform(3600, 3600*2)
            await asyncio.sleep(time)
            await self.spawn(ctx, "random event", "rand")

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
                print(f"inserted user {message.author.display_name}")
            self.client.mydb.commit()

    @commands.command()
    @commands.has_any_role(admin_id)
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
    @commands.has_any_role(admin_id)
    async def gen_roles(self, ctx):
        cursor = self.client.mydb.cursor()
        await ctx.guild.create_role(name=f"<Tarot>")
        for card in self.cards():
            role = await ctx.guild.create_role(name=f"{card.prefix}-{card.name}")
            cursor.execute("UPDATE cards_info SET role_id = ? "
                           "WHERE n = ?",
                           (role.id, card.n))
            await ctx.send(role.mention)
        await ctx.guild.create_role(name=f"</Tarot>")
        self.client.mydb.commit()

    @commands.command()
    @commands.has_any_role(admin_id)
    async def update_roles(self, ctx):
        cards = self.cards()
        for card in cards:
            role = discord.utils.get(ctx.guild.roles, id=card.role_id)
            await role.edit(name=f"{card.prefix} {card.name}", color=discord.Colour(int(card.color, 16)))

    @commands.command()
    @commands.has_any_role(admin_id)
    async def give(self, ctx, card_n, member):
        member = await Member.convert(ctx, member)
        cursor = self.client.mydb.cursor()
        if card_n == "rand":
            cursor.execute("SELECT deck_n, card_n FROM cards "
                           "WHERE user_id = 0")
        elif card_n == "new":
            cursor.execute("SELECT deck_n, card_n FROM cards "
                           "WHERE card_n NOT IN ( "
                           "SELECT card_n FROM cards "
                           "WHERE user_id=?)"
                           "AND user_id = 0",
                           (member.id,))
        else:
            cursor.execute("SELECT deck_n, card_n FROM cards "
                           "WHERE card_n = ? AND user_id = 0",
                           (card_n,))
        result = cursor.fetchone()
        if result:
            card = self.cards()[result[1]]
            cursor.execute("UPDATE cards SET user_id = ? "
                           "WHERE deck_n = ? AND card_n = ?",
                           (member.id, *result))
            self.client.mydb.commit()
            role = discord.utils.get(ctx.guild.roles, id=card.role_id)
            await ctx.send(f"{member.display_name} a obtenu la carte {role.mention}")
        elif card_n == "new":
            await ctx.send("Vous avez déjà obtenu toutes les cartes (Bravo !)\n"
                                          "Vous obtenez donc une carte aléatoire")
            await self.give(ctx, "rand", member)
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
            await self.give(ctx, result[0], ctx.author)

    @commands.command()
    @commands.has_any_role(admin_id)
    async def spawn(self, ctx, message, card_n):
        msg = await self.tarot_channel.send(message)
        await msg.add_reaction("🧙‍♀️")
        def check(reaction, user):
            return not user.bot and reaction.message.id == msg.id
        reaction, user = await self.client.wait_for('reaction_add', check=check)
        await self.give(ctx, card_n, user)

    @commands.command()
    @commands.has_any_role(admin_id)
    async def addcode(self, ctx, code, card_n="rand"):
        cursor = self.client.mydb.cursor()
        cursor.execute("INSERT INTO codes VALUES(?, 0, ?)",
                       (code, card_n))
        self.client.mydb.commit()
        await ctx.send("Code ajouté")

    @commands.command()
    async def inv(self, ctx, member=None):
        if member: member = await Member.convert(ctx, member)
        if not member:
            title = "Vos cartes : \n"
            member = ctx.author
        else:
            title = f"Cartes de {member.display_name}: \n"

        cards_info = self.cards()
        result = self.inv_dict(member)
        msg = "```diff\n"
        for i, card in enumerate(cards_info):
            count = result.get(i)
            if count:
                msg += f"+ {card.prefix:<8} {card.name:<20} x{count:<10}\n"
            else:
                msg += f"- {card.prefix:<8} {card.name:<20} x0\n"
        msg += "```"
        embed = discord.Embed(title="Inventaire", color=0x000000)
        embed.add_field(name=title, value=msg, inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def diff(self, ctx, member):
        member = await Member.convert(ctx, member)
        cards = self.cards()
        my_cards = self.inv_dict(ctx.author)
        opponent_cards = self.inv_dict(member)
        msg ="```diff\n"
        for i, card in enumerate(cards):
            me = my_cards.get(i)
            me_double = bool((my_cards.get(i) or 0) >= 2)
            opponent = opponent_cards.get(i)
            opponent_double = bool((opponent_cards.get(i) or 0) >= 2)
            if me_double and not opponent:
                msg += f"- {card.prefix:<8} {card.name:<20} \n"
            elif opponent_double and not me:
                msg += f"+ {card.prefix:<8} {card.name:<20} \n"
            else:
                msg += f"# {card.prefix:<8} {card.name:<20} \n"
        msg += "```"
        embed = discord.Embed(title="Diff", color=0x000000)
        embed.add_field(name="En rouge les cartes que vous pouvez donner\nEn vert celles qui vous intéressent", value=msg, inline=False)
        await ctx.send(embed=embed)

    def cards(self):
        cursor = self.client.mydb.cursor()
        cursor.execute("SELECT * FROM cards_info "
                       "ORDER BY n")
        return [Card(*t) for t in cursor.fetchall()]

    def inv_dict(self, member):
        cursor = self.client.mydb.cursor()
        cursor.execute("SELECT card_n, COUNT(*) FROM cards "
                       "WHERE user_id = ? "
                       "GROUP BY card_n ",
                       (member.id,))
        return dict(cursor.fetchall())

    @commands.command()
    async def show(self, ctx, number):
        card = self.cards()[int(number)]
        if card.unlocked:
            embed = discord.Embed(title=card.name,
                                  url=card.url,
                                  colour=discord.Colour(int(card.color, 16)))
            embed.set_image(url=card.url)
            embed.add_field(name=card.prefix, value=card.desc, inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Cette carte n'est pas encore disponible")

    @commands.command()
    @commands.has_any_role(admin_id)
    async def unlock(self, ctx, number: int):
        cursor = self.client.mydb.cursor()
        cursor.execute("UPDATE cards_info SET unlocked = 1 "
                       "WHERE n = ?",
                       (number,))
        self.client.mydb.commit()
        await ctx.send(f"Carte {number} débloquée")

    @commands.group()
    async def trade(self, ctx):
        if ctx.invoked_subcommand is None:
            trade, is_left = await self.find_trade(ctx)
            await trade.update(ctx)

    @trade.command()
    async def start(self, ctx, member):
        member = await Member.convert(ctx, member)
        for trade in self.trades:
            if ctx.author.id == trade.left.id or ctx.author.id == trade.right.id:
                await ctx.send(f"Vous êtes déjà en cours d'échange")
                return
            if ctx.author.id == trade.left.id or ctx.author.id == trade.right.id:
                await ctx.send(f"{member.display_name} est déjà en cours d'échange")
                return
        await ctx.send(f"Echange démaré avec {member.display_name}")
        self.trades.append(Trade(self, ctx.author, member))

    @trade.command(alias=["+"])
    async def add(self, ctx, number: int):
        trade, is_left = await self.find_trade(ctx)
        await trade.add(ctx, number, is_left)

    @trade.command(alias=["-"])
    async def rem(self, ctx, number: int):
        trade, is_left = await self.find_trade(ctx)
        await trade.rem(ctx, number, is_left)

    @trade.command()
    async def accept(self, ctx):
        trade, is_left = await self.find_trade(ctx)
        await trade.accept(ctx, is_left)

    @trade.command()
    async def decline(self, ctx):
        trade, _ = await self.find_trade(ctx)
        self.trades.remove(trade)
        await ctx.send(f"Echange annulé par {ctx.author.display_name}")

    async def find_trade(self, ctx):
        for trade in self.trades:
            if ctx.author.id == trade.left_side.member.id:
                return trade, True
            if ctx.author.id == trade.right_side.member.id:
                return trade, False
        await ctx.send("Aucun échange en cours")


def setup(client):
    client.add_cog(Tarot(client))
