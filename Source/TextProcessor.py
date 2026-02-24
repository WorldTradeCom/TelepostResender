from dataclasses import dataclass
from typing import TYPE_CHECKING
import asyncio

from nltk.sentiment import SentimentIntensityAnalyzer
from deep_translator import GoogleTranslator
import nltk

if TYPE_CHECKING:
	from dublib.Engine.Configurator import Config

#==========================================================================================#
# >>>>> ВСПОМОГАТЕЛЬНЫЕ СТРУКТУРЫ ДАННЫХ <<<<< #
#==========================================================================================#

@dataclass(frozen = True)
class PolarityScores:
	neg: float
	neu: float
	pos: float
	compound: float

#==========================================================================================#
# >>>>> ОСНОВНОЙ КЛАСС <<<<< #
#==========================================================================================#

class TextProcessor:
	"""Обработчик пересылаемого текста."""

	def __init__(self, settings: "Config"):
		"""
		Оператор пересылки постов.

		:param settings: Глобальные настройки.
		:type settings: Config
		"""
		
		self.__Settings = settings

		nltk.download("vader_lexicon")
		self.__SentimentAnalyzer = SentimentIntensityAnalyzer()
		self.__Translator = GoogleTranslator(source = "ru", target = "en")

	async def analyze_polarity(self, text: str) -> PolarityScores:
		"""
		Анализирует эмоциональную полярность текста.

		:param text: Анализируемый текст.
		:type text: str
		:return: Долевая оценка эмоциональной полярности.
		:rtype: PolarityScores
		"""

		text = await asyncio.to_thread(self.__Translator.translate, text)
		Scores = await asyncio.to_thread(self.__SentimentAnalyzer.polarity_scores, text)

		return PolarityScores(Scores["neg"], Scores["neu"], Scores["pos"], Scores["compound"])

	async def filter_paragraphs(self, text: str) -> str:
		"""
		Удаляет абзацы из текста по ключевым нежелательным фразам.

		:param text: Обрабатываемый текст.
		:type text: str | None
		:return: Текст сообщения или `None` в случае игнорирования.
		:rtype: str | None
		"""

		Buffer = list()

		for Line in text.split("\n"):
			IsFiltered = False

			for BadWord in self.__Settings["text_processor"]["exclude_paragraphs_by_badwords"]:
				if BadWord in Line:
					IsFiltered = True
					break
			
			if not IsFiltered: Buffer.append(Line)		

		return "\n".join(Buffer)
	
	async def translate_to_buzzers(self, text: str) -> str | None:
		"""
		Переводит текст на зумерский язык при помощи **Buzzer Mutarji**. Если не указан каталог переводчика, вернёт исходную строку.

		:param text: Текст сообщения.
		:type text: str
		:return: Обработанный текст или `None` в случае ошибки.
		:rtype: str | None
		"""

		Additional = " ".join(self.__Settings["text_processor"]["buzzerator_requests"]).strip()
		if Additional: Additional = f" --additional \"{Additional}\""

		if not self.__Settings["text_processor"]["buzzer_mutarji_directory"]: return text
		Command = "cd " + self.__Settings["text_processor"]["buzzer_mutarji_directory"] + f" && . .venv/bin/activate && python main.py translate -to \"{text}\"{Additional}"
		Process = await asyncio.create_subprocess_shell(Command, stdout = asyncio.subprocess.PIPE, stderr = asyncio.subprocess.PIPE)
		stdout, stderr = await Process.communicate()
		stdout, stderr = stdout.decode().strip(), stderr
		if stderr or stdout == "None" or "Generation failed with response JSON" in stdout: return

		return stdout