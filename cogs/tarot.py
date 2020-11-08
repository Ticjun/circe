import typing
from discord.ext import commands, tasks
from botpersistent import Module
import discord
import random
import asyncio


class Side:
    def __init__(self, member):
        self.member = member
        self.trade = {}
        self.ok = False


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

    async def add(self, ctx, number: int, is_left):
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

    async def rem(self, ctx, number: int, is_left):
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
        embed = discord.Embed(title="Echange", description="<->", color=0x000000)
        embed.add_field(name=self.left_side.member.display_name, value=self.stringify(self.left_side), inline=True)
        embed.add_field(name=self.right_side.member.display_name, value=self.stringify(self.right_side), inline=True)
        await ctx.send(embed=embed)

    def stringify(self, side):
        str = ""
        card_infos = self.cog.infos()
        for card_n, count in list(side.trade.items()):
            str += f"{card_infos[card_n][0]}-{card_infos[card_n][1]} x{count}\n"
        if not str: str += "Rien"
        if side.ok: str = "✅\n" + str
        else: str = "❎\n" + str
        return str

    def execute(self):
        cursor = self.cog.client.mydb.cursor()
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
        self.cog.client.mydb.commit()


class Tarot(Module):
    def __init__(self, client):
        super().__init__(client)
        self.n_decks = 2
        self.n_cards = 22
        self.trades = []

    @commands.Cog.listener()
    async def on_ready(self):
        self.tarot_channel = self.client.get_channel(774795918557708318)
        self.redeem_channel = self.client.get_channel(774622426080083999)
        await self.random_spawn()

    async def random_spawn(self):
        while True:
            time = random.uniform(10, 100)
            await asyncio.sleep(time)
            await self.spawn(None, "random event", "rand")

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
        cursor = self.client.mydb.cursor()
        if card_n == "rand":
            cursor.execute("SELECT deck_n, card_n FROM cards "
                           "WHERE user_id = 0")
        elif card_n == "new":
            cursor.execute("SELECT deck_n, card_n FROM cards "
                           "WHERE card_n NOT IN")
        else:
            cursor.execute("SELECT deck_n, card_n FROM cards "
                           "WHERE card_n = ? AND user_id = 0",
                           (card_n,))

        result = cursor.fetchone()
        if result:
            cursor.execute("UPDATE cards SET user_id = ? "
                           "WHERE deck_n = ? AND card_n = ?",
                           (member.id, *result))
            self.client.mydb.commit()
            await self.tarot_channel.send(f"{member.display_name} a obtenu la carte {result[1]}")
        elif card_n == "new":
            await self.tarot_channel.send("Vous avez déjà obtenu toutes les cartes (Bravo !)"
                           "Vous obtenez donc une carte aléatoire")
            await self.give(None, "rand", member)
        else:
            await self.tarot_channel.send("Carte introuvable !")

    @commands.command()
    async def redeem(self, ctx, code):
        if ctx.channel.id != self.redeem_channel:
            return
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
            await self.give(None, result[0], ctx.author)

    @commands.command()
    @commands.has_any_role("Circé")
    async def spawn(self, ctx, message, card_n):
        msg = await self.tarot_channel.send(message)
        await msg.add_reaction("🧙")
        def check(reaction, user):
            return not user.bot and reaction.message.id == msg.id
        reaction, user = await self.client.wait_for('reaction_add', check=check)
        await self.give(None, card_n, user)

    @commands.command()
    @commands.has_any_role("Circé")
    async def addcode(self, ctx, code, card_n="rand"):
        cursor = self.client.mydb.cursor()
        cursor.execute("INSERT INTO codes VALUES(?, 0, ?)",
                       (code, card_n))
        self.client.mydb.commit()
        await ctx.send("Code ajouté")

    @commands.command()
    async def inv(self, ctx, member: typing.Optional[discord.Member]):
        if not member:
            msg = "Vos cartes : \n"
            member = ctx.author
        else:
            msg = msg = f"Cartes de {member.display_name}: \n"

        cards_info = self.infos()
        result = self.inv_dict(member)

        msg +="```diff\n"
        for i, (prefix, name) in enumerate(cards_info):
            count = result.get(i)
            if count:
                msg += f"+ {prefix:<8} {name:<20} x{count:<10}\n"
            else:
                msg += f"# {prefix:<8} {name:<20} x0\n"
        msg += "```"
        await ctx.send(msg)

    @commands.command()
    async def diff(self, ctx, member: discord.Member):
        cards_info = self.infos()
        my_cards = self.inv_dict(ctx.author)
        opponent_cards = self.inv_dict(member)
        msg ="Diff : \n```diff\n"
        for i, (prefix, name) in enumerate(cards_info):
            me = my_cards.get(i)
            me_double = bool((my_cards.get(i) or 0) >= 2)
            opponent = opponent_cards.get(i)
            opponent_double = bool((opponent_cards.get(i) or 0) >= 2)
            if me_double and not opponent:
                msg += f"- {prefix:<8} {name:<20} \n"
            elif opponent_double and not me:
                msg += f"+ {prefix:<8} {name:<20} \n"
            else:
                msg += f"# {prefix:<8} {name:<20} \n"
        msg += "```"
        await ctx.send(msg)

    def infos(self):
        cursor = self.client.mydb.cursor()
        cursor.execute("SELECT prefix, name FROM cards_info")
        return cursor.fetchall()

    def inv_dict(self, member):
        cursor = self.client.mydb.cursor()
        cursor.execute("SELECT card_n, COUNT(*) FROM cards "
                       "WHERE user_id = ? "
                       "GROUP BY card_n ",
                       (member.id,))
        return dict(cursor.fetchall())

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

    @commands.group()
    async def trade(self, ctx):
        if ctx.invoked_subcommand is None:
            trade, is_left = await self.find_trade(ctx)
            await trade.update(ctx)

    @trade.command()
    async def start(self, ctx, member: discord.Member):
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
        self.trades.pop(trade)
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
