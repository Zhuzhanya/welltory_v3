"""
bot.py — главный файл Telegram-бота
Запуск: python bot.py
"""

import logging
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from config import TELEGRAM_TOKEN
from database import Database
from ai_processor import AIProcessor
from report_generator import ReportGenerator

# Логирование — чтобы видеть что происходит в консоли
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализируем наши модули
db = Database()
ai = AIProcessor()
reporter = ReportGenerator(db)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start — приветствие"""
    user_id = update.effective_user.id
    name = update.effective_user.first_name

    db.ensure_user_exists(user_id)

    await update.message.reply_text(
        f"Привет, {name}! 👋\n\n"
        "Я помогаю отслеживать твои симптомы и готовить отчёты для врача.\n\n"
        "📝 Просто пиши мне как чувствуешь себя — в любой форме:\n"
        "→ «с утра болела голова, несильно»\n"
        "→ «давление 130/85, немного кружится голова»\n"
        "→ «после еды тошнит уже второй день»\n\n"
        "Команды:\n"
        "/report — отчёт за последние 7 дней\n"
        "/history — все записи\n"
        "/help — помощь"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    await update.message.reply_text(
        "🆘 Как пользоваться ботом:\n\n"
        "1. Просто пиши симптомы обычным текстом\n"
        "2. Можно писать по-русски или по-английски\n"
        "3. Указывай когда началось, как сильно, что помогло\n\n"
        "Примеры:\n"
        "• «3 дня болит правый бок при вдохе»\n"
        "• «температура 37.8, слабость»\n"
        "• «выпил ибупрофен, стало лучше через час»\n\n"
        "Команды:\n"
        "/report — сводный отчёт для врача\n"
        "/history — хронология всех записей\n"
        "/clear — очистить все мои данные"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем любое текстовое сообщение от пользователя"""
    user_id = update.effective_user.id
    raw_text = update.message.text

    db.ensure_user_exists(user_id)

    # 1. Сохраняем сырое сообщение (всегда, даже если AI сломается)
    message_id = db.save_raw_message(user_id, raw_text)

    # 2. Отправляем "печатает..." пока AI работает
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # 3. Отправляем в AI для структурирования
    structured = ai.process_message(raw_text)

    if structured and structured.get("symptoms"):
        # 4. Сохраняем извлечённые симптомы
        db.save_symptoms(message_id, user_id, structured["symptoms"])

        symptom_names = [s["name"] for s in structured["symptoms"]]
        symptoms_text = ", ".join(symptom_names)

        await update.message.reply_text(
            f"✅ Записано!\n"
            f"📋 Обнаружил: {symptoms_text}\n\n"
            f"Продолжай писать — всё сохраняется в твою историю."
        )
    else:
        # AI не нашёл симптомов — но сообщение всё равно сохранено
        await update.message.reply_text(
            "📝 Записал твоё сообщение.\n"
            "Не смог распознать конкретные симптомы — но текст сохранён."
        )


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /report — генерирует PDF-отчёт для врача"""
    import os
    user_id = update.effective_user.id

    await update.message.reply_text("⏳ Готовлю PDF-отчёт...")

    pdf_path = reporter.generate_pdf_report(user_id, days=7)

    if not pdf_path:
        await update.message.reply_text(
            "📭 Нет данных за последние 7 дней.\nНапиши несколько сообщений о своём самочувствии!"
        )
        return

    with open(pdf_path, "rb") as pdf_file:
        await update.message.reply_document(
            document=pdf_file,
            filename="health_report.pdf",
            caption="🏥 Отчёт готов! Можешь переслать его врачу."
        )

    os.remove(pdf_path)


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /history — хронология всех записей"""
    user_id = update.effective_user.id

    messages = db.get_all_messages(user_id)

    if not messages:
        await update.message.reply_text("У тебя пока нет записей.")
        return

    history_text = "📅 *Твоя история симптомов:*\n\n"
    for msg in messages[-20:]:  # Последние 20 записей
        date_str = msg["timestamp"][:10]  # Только дата YYYY-MM-DD
        history_text += f"*{date_str}*: {msg['raw_text'][:100]}...\n\n"

    await update.message.reply_text(history_text, parse_mode="Markdown")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /clear — очистить данные пользователя"""
    user_id = update.effective_user.id
    db.clear_user_data(user_id)
    await update.message.reply_text("🗑 Все твои данные удалены.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем голосовые сообщения — транскрибируем через Whisper и обрабатываем как текст"""
    user_id = update.effective_user.id
    db.ensure_user_exists(user_id)

    await update.message.reply_text("🎤 Получила голосовое, транскрибирую...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # 1. Скачиваем голосовой файл от Telegram
    voice = update.message.voice
    voice_file = await context.bot.get_file(voice.file_id)
    ogg_path = f"voice_{user_id}.ogg"
    await voice_file.download_to_drive(ogg_path)

    try:
        # 2. Отправляем в OpenAI Whisper для транскрипции
        from config import OPENAI_API_KEY
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        with open(ogg_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru"  # подсказываем что русский — точнее распознаёт
            )

        raw_text = transcription.text
        await update.message.reply_text(f"📝 Распознала: «{raw_text}»")

        # 3. Дальше всё как обычно — сохраняем и обрабатываем AI
        message_id = db.save_raw_message(user_id, raw_text)
        structured = ai.process_message(raw_text)

        if structured and structured.get("symptoms"):
            db.save_symptoms(message_id, user_id, structured["symptoms"])
            symptom_names = [s["name"] for s in structured["symptoms"]]
            await update.message.reply_text(
                f"✅ Записано!\n"
                f"📋 Обнаружила: {', '.join(symptom_names)}"
            )
        else:
            await update.message.reply_text(
                "📝 Записала твоё сообщение.\n"
                "Конкретных симптомов не распознала — но текст сохранён."
            )

    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await update.message.reply_text(
            "❌ Не удалось обработать голосовое. Попробуй написать текстом."
        )
    finally:
        # Удаляем временный файл
        if os.path.exists(ogg_path):
            os.remove(ogg_path)


def main():
    """Запуск бота"""
    # Создаём таблицы в БД при старте
    db.create_tables()

    # Создаём приложение
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Регистрируем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("clear", clear_command))

    # Обработчик всех текстовых сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Обработчик голосовых сообщений
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("Бот запущен. Нажми Ctrl+C для остановки.")
    app.run_polling()


if __name__ == "__main__":
    main()
