from typing import TYPE_CHECKING
import asyncio

from telethon import TelegramClient

if TYPE_CHECKING:
	from dublib.Engine.Configurator import Config

	from telethon.types import Message

class Resender:
	"""Оператор пересылки постов."""

	#==========================================================================================#
	# >>>>> СВОЙСТВА <<<<< #
	#==========================================================================================#

	@property
	def from_chat_url(self) -> str:
		"""URL источника постов."""

		return "https://t.me/" + self.__Settings["from"]

	@property
	def last_resended_id(self) -> int | None:
		"""ID последнего пересланного сообщения."""

		return self.__Settings["last_resended_id"]

	#==========================================================================================#
	# >>>>> ПУБЛИЧНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

	def __init__(self, settings: "Config"):
		"""
		Оператор пересылки постов.

		:param settings: Глобальные настройки.
		:type settings: Config
		"""
		
		self.__Settings = settings

		self.__Client = TelegramClient(
			".session",
			self.__Settings["api_id"],
			self.__Settings["api_hash"],
			device_model = "Pixel 5",
			system_version = "11",
			app_version = "8.4.1",
			lang_code = "en",
			system_lang_code = "en-US"
		)

	async def connect(self):
		"""Выполняет подключение к серверу."""

		await self.__Client.start(self.__Settings["phone_number"])

	async def get_unsended_messages(self) -> "tuple[Message]":
		"""
		Возвращает последовательность не пересланных сообщений.

		При первом запуске получает только последнее сообщение.

		:return: Последовательность сообщений.
		:rtype: tuple[Message]
		"""

		UnsendedMessages: "list[Message]" = list()

		if not self.last_resended_id:
			async for CurrentMessage in self.__Client.iter_messages(self.from_chat_url, limit = 1):
				CurrentMessage: "Message"
				UnsendedMessages.append(CurrentMessage)
				self.__Settings.set("last_resended_id", CurrentMessage.id)

		else:
			async for CurrentMessage in self.__Client.iter_messages(self.from_chat_url, min_id = self.last_resended_id):
				UnsendedMessages.append(CurrentMessage)

			if UnsendedMessages: self.__Settings.set("last_resended_id", UnsendedMessages[-1].id)

		return tuple(UnsendedMessages)
	
	async def resend_messages(self):
		"""Запускает пересылку сообщений."""

		Messages: "tuple[Message]" = await self.get_unsended_messages()

		for CurrentMessage in Messages:
			CurrentMessage: "Message"
			Text = CurrentMessage.message
			if self.__Settings["buzzer_mutarji_directory"]: Text = await self.translate(Text)

			if CurrentMessage.media:
				await self.__Client.send_file(
					self.__Settings["to"],
					file = CurrentMessage.media,
					caption = Text
				)

			else:
				await self.__Client.send_message(self.__Settings["to"], message = Text)

	async def translate(self, text: str) -> str | None:
		"""
		Переводит текст на зумерский язык при помощи **Buzzer Mutarji**.

		:param text: Текст сообщения.
		:type text: str
		:return: Переведённый текст или `None` в случае ошибки.
		:rtype: str | None
		"""

		Command = "cd " + self.__Settings["buzzer_mutarji_directory"] + f" && . .venv/bin/activate && python main.py translate -to \"{text}\""
		Process = await asyncio.create_subprocess_shell(Command, stdout = asyncio.subprocess.PIPE, stderr = asyncio.subprocess.PIPE)
		stdout, stderr = await Process.communicate()
		stdout, stderr = stdout.decode().strip(), stderr
		if stderr: return

		Lines = stdout.split("\n")
		Buffer = list()

		# Фильтрация строк по ключевым фразам.
		for Line in Lines:
			IsFiltered = False

			for BadWord in self.__Settings["badwords"]:
				if BadWord in Line:
					IsFiltered = True
					break
			
			if not IsFiltered: Buffer.append(Line)		

		return "\n".join(Buffer)