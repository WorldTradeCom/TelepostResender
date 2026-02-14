from Source.Resender import Resender

from dublib.Engine.Configurator import Config

import asyncio

async def main():
	Settings = Config("Settings.json")
	Settings.load()
	Operator = Resender(Settings)
	await Operator.connect()
	await Operator.resend_messages()

asyncio.run(main())