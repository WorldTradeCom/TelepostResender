from Source.TextProcessor import TextProcessor

from typing import TYPE_CHECKING

from telethon import TelegramClient

if TYPE_CHECKING:
	from dublib.Engine.Configurator import Config

	from telethon.tl.custom.message import Message

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
		self.__Client.parse_mode = "html"
		self.__TextProcessor = TextProcessor(self.__Settings)

	async def is_message_resendable(self, message: "Message") -> bool:
		"""
		Проверяет, требуется ли пересылать текущее сообщение.

		:param message: Данные сообщения.
		:type message: Message
		:return: Возвращает `True`, если сообщение следует переслать.
		:rtype: bool
		"""
		
		if self.__Settings["text_processor"]["sentiment_compound"] != None:
			PolarityScore = await self.__TextProcessor.analyze_polarity(message.text)
			if PolarityScore.compound <= self.__Settings["text_processor"]["sentiment_compound"]: return False

		return True

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

		else:
			async for CurrentMessage in self.__Client.iter_messages(self.from_chat_url, min_id = self.last_resended_id):
				UnsendedMessages.append(CurrentMessage)

		return tuple(reversed(UnsendedMessages))
	
	async def resend_messages(self):
		"""Запускает пересылку сообщений."""

		for CurrentMessage in await self.get_unsended_messages():

			if not await self.is_message_resendable(CurrentMessage): continue
			Text = await self.__TextProcessor.filter_paragraphs(CurrentMessage.text)

			if Text:
				Text = await self.__TextProcessor.translate_to_buzzers(Text)
				if not Text: continue

			if CurrentMessage.media:
				await self.__Client.send_file(
					self.__Settings["to"],
					file = CurrentMessage.media,
					caption = Text
				)

			else:
				await self.__Client.send_message(self.__Settings["to"], message = Text)

			self.__Settings.set("last_resended_id", CurrentMessage.id)