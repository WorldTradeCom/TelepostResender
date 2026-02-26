from Source.TextProcessor import TextProcessor

from dublib.Methods.Filesystem import ReadTextFile, WriteTextFile

from dataclasses import dataclass
from typing import TYPE_CHECKING
import asyncio
import os

from telethon import TelegramClient

if TYPE_CHECKING:
	from dublib.Engine.Configurator import Config

	from telethon.tl.types import MessageMediaDocument
	from telethon.tl.custom.message import Message

@dataclass
class MessageData:
	attachments: "tuple[MessageMediaDocument]"
	last_id: int
	text: str | None

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
	def to_chat_url(self) -> str:
		"""URL целевого канала."""

		return "https://t.me/" + self.__Settings["to"]

	@property
	def last_resended_id(self) -> int | None:
		"""ID последнего пересланного сообщения."""

		return self.__LastID

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

	def __GetLastResendedMessageID(self) -> int | None:
		"""
		Возвращает ID последнего пересланного сообщения.

		:return: ID сообщения или `None` при отсутствии записи.
		:rtype: int
		"""

		if os.path.exists(self.__FilePathForLastID): return int(ReadTextFile(self.__FilePathForLastID, strip = True))

	def __SetLastResendedMessageID(self, id: int):
		"""
		Записывает ID последнего пересланного сообщения.

		:param id: ID сообщения
		:type id: int
		"""

		WriteTextFile(self.__FilePathForLastID, str(id))

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

		self.__FilePathForLastID = ".last.txt"
		self.__LastID = self.__GetLastResendedMessageID()

	async def connect(self):
		"""Выполняет подключение к серверу."""

		await self.__Client.start(self.__Settings["phone_number"], max_attempts = 1)

	async def get_message_data(self, message: "Message") -> MessageData:
		"""
		Возвращает набор вложений для сообщения.

		:param message: Данные сообщения.
		:type message: Message
		:return: Набор вложений.
		:rtype: tuple[MessageMediaDocument]
		"""

		Attachments = list()
		LastID = message.id
		Text = message.text

		if message.media:
			Attachments.append(message.media)

			if message.grouped_id:
				async for CurrentMessage in self.__Client.iter_messages(self.__Settings["from"], min_id = message.id, reverse = True):
					CurrentMessage: "Message"
					if CurrentMessage.grouped_id == message.grouped_id:
						if not Text: Text = CurrentMessage.text
						if CurrentMessage.id > LastID: LastID = CurrentMessage.id
						Attachments.append(CurrentMessage.media)

					else: break

		return MessageData(tuple(Attachments), LastID, Text)

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
	
	async def is_message_resendable(self, text: str) -> bool:
		"""
		Проверяет, требуется ли пересылать текущее сообщение.

		:param text: Текст сообщения
		:type text: str
		:return: Возвращает `True`, если сообщение следует переслать.
		:rtype: bool
		"""
		
		if self.__Settings["text_processor"]["sentiment_compound"] != None:
			PolarityScore = await self.__TextProcessor.analyze_polarity(text)
			if PolarityScore.compound <= self.__Settings["text_processor"]["sentiment_compound"]: return False

		for Badword in self.__Settings["text_processor"]["skip_messages_by_badwords"]:
			if Badword in text: return False

		return True

	async def resend_messages(self):
		"""Запускает пересылку сообщений."""

		for CurrentMessage in await self.get_unsended_messages():
			Data = await self.get_message_data(CurrentMessage)

			if self.last_resended_id and CurrentMessage.id <= self.last_resended_id:
				print(f"Message {CurrentMessage.id} skipped.")
				continue
			
			if not Data.text or not await self.is_message_resendable(Data.text):
				print(f"Message {CurrentMessage.id} filtered.")
				self.__SetLastResendedMessageID(Data.last_id)
				continue

			Text = await self.__TextProcessor.filter_paragraphs(Data.text)

			if Text:
				Text = await self.__TextProcessor.translate_to_buzzers(Text)
				if not Text:
					print(f"Unable translate message {CurrentMessage.id}.")
					continue

			if Text: Text = await self.__TextProcessor.remove_tags(Text)

			Sign = self.__Settings["text_processor"]["sign"]
			if Sign:
				Text = Text.rstrip() + f"\n\n<a href=\"{self.to_chat_url}\">{Sign}</a>"
			
			if Data.attachments:
				Count = len(Data.attachments)
				await self.__Client.send_file(
					self.__Settings["to"],
					file = Data.attachments,
					caption = Text
				)
				self.__SetLastResendedMessageID(Data.last_id)
				print(f"Message {CurrentMessage.id} sended with {Count} attachments.")

			else:
				await self.__Client.send_message(self.__Settings["to"], message = Text, link_preview = False)
				self.__SetLastResendedMessageID(CurrentMessage.id)
				print(f"Message {CurrentMessage.id} sended.")