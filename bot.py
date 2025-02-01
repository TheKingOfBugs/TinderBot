import os
from enum import Enum
from functools import wraps
from typing import Dict
from dotenv import load_dotenv

from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from telegram import Update, ParseMode
from gpt import ChatGptService  # Ваш модуль для работы с GPT
from util import (  # Ваши утилиты
    load_message,
    send_photo,
    send_text,
    load_prompt,
    dialog_user_info_to_str,
    send_text_buttons,
)

# Загрузка переменных окружения
load_dotenv()
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
GPT_TOKEN = os.getenv("CHATGPT_TOKEN")

# Тип контекста
type_context = ContextTypes.DEFAULT_TYPE


# Перечисление режимов работы
class Mode(str, Enum):
    MAIN = "main"
    GPT = "gpt"
    DATE = "date"
    PROFILE = "profile"
    OPENER = "opener"
    MESSAGE = "message"


# Класс для хранения данных пользователя
class UserData:
    def __init__(self):
        self.mode: Mode = None
        self.count: int = 0
        self.user_info: Dict = {}
        self.message_history: list = []
        self.current_prompt: str = None


# Инициализация сервиса ChatGPT
chatgpt = ChatGptService(token=GPT_TOKEN)


# Декоратор для обработки ошибок
def error_handler(func):
    @wraps(func)
    async def wrapper(update: Update, context: type_context, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
            await send_text(update, context, "⚠️ Произошла ошибка. Попробуйте еще раз.")

    return wrapper


# Утилиты для работы с пользовательскими данными
def get_user_data(context: type_context) -> UserData:
    if "user_data" not in context.user_data:
        context.user_data["user_data"] = UserData()
    return context.user_data["user_data"]


def reset_user_data(user_data: UserData):
    user_data.mode = None
    user_data.count = 0
    user_data.user_info.clear()
    user_data.message_history.clear()
    user_data.current_prompt = None


# Унифицированная функция отправки
async def send_response(
        update: Update,
        context: type_context,
        template_name: str,
        buttons: Dict = None
):
    await send_photo(update, context, template_name)
    text = load_message(template_name)

    if buttons:
        await send_text_buttons(update, context, text, buttons)
    else:
        await send_text(update, context, text)


# Обработчики команд
@error_handler
async def start(update: Update, context: type_context):
    user_data = get_user_data(context)
    user_data.mode = Mode.MAIN

    await send_response(update, context, "main")

    await show_main_menu(update, context)


async def show_main_menu(update: Update, context: type_context):
    buttons = {
        "start": "главное меню бота",
        "profile": "генерация Tinder-профиля 😎",
        "opener": "сообщение для знакомства 🥰",
        "message": "переписка от вашего имени 😈",
        "date": "переписка со звездами 🔥",
        "gpt": "задать вопрос чату GPT 🧠",
    }
    await send_text_buttons(update, context, "Выберите действие:", buttons)


@error_handler
async def gpt(update: Update, context: type_context):
    user_data = get_user_data(context)
    user_data.mode = Mode.GPT
    await send_response(update, context, "gpt")


@error_handler
async def date(update: Update, context: type_context):
    user_data = get_user_data(context)
    user_data.mode = Mode.DATE
    await send_response(
        update,
        context,
        "date",
        buttons={
            "date_grande": "Ариана Гранде",
            "date_robbie": "Марго Робби",
            "date_zendaya": "Зендея",
            "date_gosling": "Райан Гослинг",
            "date_hardy": "Том Харди"
        }
    )


@error_handler
async def profile(update: Update, context: type_context):
    user_data = get_user_data(context)
    user_data.mode = Mode.PROFILE
    reset_user_data(user_data)
    await send_response(update, context, "profile")
    await send_text(update, context, "Сколько вам лет?")


@error_handler
async def opener(update: Update, context: type_context):
    user_data = get_user_data(context)
    user_data.mode = Mode.OPENER
    reset_user_data(user_data)
    await send_response(update, context, "opener")
    await send_text(update, context, "Имя девушки?")


@error_handler
async def message(update: Update, context: type_context):
    user_data = get_user_data(context)
    user_data.mode = Mode.MESSAGE
    reset_user_data(user_data)
    await send_response(
        update,
        context,
        "message",
        buttons={
            "message_next": "Написать сообщение",
            "message_date": "Пригласить на свидание",
        }
    )


# Обработчики кнопок
@error_handler
async def date_button(update: Update, context: type_context):
    query = update.callback_query
    await query.answer()

    user_data = get_user_data(context)
    user_data.current_prompt = query.data

    await send_photo(update, context, query.data)
    await send_text(
        update,
        context,
        "Отличный выбор! Пригласите девушку (Парня) на 5 сообщений.",
        parse_mode=ParseMode.HTML
    )


@error_handler
async def message_button(update: Update, context: type_context):
    query = update.callback_query
    await query.answer()

    user_data = get_user_data(context)
    prompt = load_prompt(query.data)

    user_chat_history = "\n\n".join(user_data.message_history)
    answer = await chatgpt.send_question(prompt, user_chat_history)

    await send_text(update, context, answer)


# Обработчики диалогов
@error_handler
async def handle_message(update: Update, context: type_context):
    user_data = get_user_data(context)
    text = update.message.text

    if user_data.mode == Mode.GPT:
        await handle_gpt_dialog(update, context, text)
    elif user_data.mode == Mode.DATE:
        await handle_date_dialog(update, context, text)
    elif user_data.mode == Mode.PROFILE:
        await handle_profile_dialog(update, context, text)
    elif user_data.mode == Mode.OPENER:
        await handle_opener_dialog(update, context, text)
    elif user_data.mode == Mode.MESSAGE:
        await handle_message_dialog(update, context, text)
    else:
        await handle_default_response(update, context, text)


async def handle_gpt_dialog(update: Update, context: type_context, text: str):
    prompt = load_prompt("gpt")
    answer = await chatgpt.send_question(prompt, text)
    await send_text(update, context, answer)


async def handle_date_dialog(update: Update, context: type_context, text: str):
    user_data = get_user_data(context)
    user_data.message_history.append(text)

    if len(user_data.message_history) >= 5:
        prompt = load_prompt(user_data.current_prompt)
        history = "\n".join(user_data.message_history[-5:])
        answer = await chatgpt.send_question(prompt, history)
        await send_text(update, context, answer)
        reset_user_data(user_data)
    else:
        await send_text(update, context, f"Сообщение {len(user_data.message_history)}/5 принято!")


async def handle_profile_dialog(update: Update, context: type_context, text: str):
    user_data = get_user_data(context)

    questions = [
        ("age", "Сколько вам лет?", "Кем вы работаете?"),
        ("occupation", "Кем вы работаете?", "У вас есть хобби?"),
        ("hobby", "У вас есть хобби?", "Что вам НЕ нравится в людях?"),
        ("annoys", "Что вам НЕ нравится в людях?", "Цель знакомства?"),
        ("goals", "Цель знакомства?", None),
    ]

    if user_data.count < len(questions):
        key, current_question, next_question = questions[user_data.count]
        user_data.user_info[key] = text
        user_data.count += 1

        if next_question:
            await send_text(update, context, next_question)
        else:
            prompt = load_prompt("profile")
            user_info_str = dialog_user_info_to_str(user_data.user_info)
            answer = await chatgpt.send_question(prompt, user_info_str)
            await send_text(update, context, answer)
            reset_user_data(user_data)


async def handle_opener_dialog(update: Update, context: type_context, text: str):
    user_data = get_user_data(context)

    questions = [
        ("name", "Имя девушки?", "Сколько ей лет?"),
        ("age", "Сколько ей лет?", "Оцените ее внешность: 1-10 баллов?"),
        ("looks_score", "Оцените ее внешность: 1-10 баллов?", "Кем она работает?"),
        ("occupation", "Кем она работает?", "Что вам в ней нравится?"),
        ("likes", "Что вам в ней нравится?", None),
    ]

    if user_data.count < len(questions):
        key, current_question, next_question = questions[user_data.count]
        user_data.user_info[key] = text
        user_data.count += 1

        if next_question:
            await send_text(update, context, next_question)
        else:
            prompt = load_prompt("opener")
            user_info_str = dialog_user_info_to_str(user_data.user_info)
            answer = await chatgpt.send_question(prompt, user_info_str)
            await send_text(update, context, answer)
            reset_user_data(user_data)


async def handle_message_dialog(update: Update, context: type_context, text: str):
    user_data = get_user_data(context)
    user_data.message_history.append(text)
    await send_text(update, context, "Сообщение сохранено в истории")


async def handle_default_response(update: Update, context: type_context, text: str):
    await send_text(update, context, "Привет! Я готов вам помочь 😊")
    await send_photo(update, context, "avatar_main")
    await show_main_menu(update, context)


# Инициализация приложения
app = ApplicationBuilder().token(TG_TOKEN).build()

# Регистрация обработчиков
handlers = [
    CommandHandler("start", start),
    CommandHandler("gpt", gpt),
    CommandHandler("date", date),
    CommandHandler("profile", profile),
    CommandHandler("opener", opener),
    CommandHandler("message", message),
    CallbackQueryHandler(date_button, pattern="^date_.*"),
    CallbackQueryHandler(message_button, pattern="^message_.*"),
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
]

for handler in handlers:
    app.add_handler(handler)

# Запуск бота
if __name__ == "__main__":
    print("Бот запущен...")
    app.run_polling()