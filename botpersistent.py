from discord.ext import commands
import discord
import dataclasses
import json
import os

LOCAL_FILE = "local.json"
CONFIG_FILE = "config.json"

class DataclassJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)

class BotPersistent(commands.Bot):
    def __init__(self, *args, **kwargs):
        # Check if local config file exists, if not, load default config
        if os.path.isfile(LOCAL_FILE):
            with open(LOCAL_FILE, "r") as read_file:
                self.data = json.load(read_file)["Bot"]
        else:
            with open(CONFIG_FILE, "r") as read_file:
                self.data = json.load(read_file)["Bot"]
            with open(LOCAL_FILE, "w+") as write_file:
                json.dump(self.data, write_file, cls=DataclassJSONEncoder)

        if self.data["proxy"]:
            kwargs["proxy"] = self.data["proxy"]
        super().__init__(*args, **kwargs)

    def save(self):
        d = {"Bot": self.data}
        for cog in self.cogs.values():
            d[cog.qualified_name] = cog.data
        with open(LOCAL_FILE, "w+") as write_file:
            json.dump(d, write_file, cls=DataclassJSONEncoder)
        print("[Bot] Saved config")

    async def close(self):
        await super().close()


class Module(commands.Cog):
    def __init__(self, client):
        self.client = client
        with open(LOCAL_FILE, "r") as read_file:
            self.data = json.load(read_file).get(self.qualified_name)
        if self.data is None:
            with open(CONFIG_FILE, "r") as read_file:
                self.data = json.load(read_file).get(self.qualified_name)
