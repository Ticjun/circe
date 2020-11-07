from discord.ext import commands
from botpersistent import Module


class Tarot(Module):
    def __init__(self, client):
        super().__init__(client)

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


def setup(client):
    client.add_cog(Tarot(client))
