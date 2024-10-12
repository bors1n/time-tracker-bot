import sqlite3
import time
import warnings
from importlib.metadata import entry_points
from sqlite3 import IntegrityError
import os

from anyio import current_time

from setup_db import create_tables
from export_data import export_user_data
from connect_to_database import database_connection
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, ConversationHandler, MessageHandler, Filters
#from settings import TG_TOKEN

import logging

from utils.time_calculations import TimeTracker

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore")

# Определяем состояния для ConversationHandler
CREATE_PROJECT, SELECTION_PROJECT, TRACK_TIME = range(3)

# Функция для регистрации пользователей
def register_user(user_id, username):
    with database_connection() as (conn, cursor):
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()

# Создания нового проекта
def create_new_project(user_id, project_name):
    with database_connection() as (conn, cursor):
        cursor.execute("INSERT INTO projects (user_id, project_name) VALUES (?, ?)", (user_id, project_name))
        conn.commit()

# Получение id проекта
def get_project_id(user_id, project_name):
    with database_connection() as (conn, cursor):
        cursor.execute("SELECT project_id FROM projects WHERE user_id=? AND project_name=?", (user_id, project_name))
        return cursor.fetchone()[0]

# Фукнция для отправки кнопки Start при запуске бота
def start(update: Update, context: CallbackContext) -> None:
    keyboard = [[KeyboardButton("Приступить")],
                [KeyboardButton("Выгрузить данные")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    message_text = ("Привет\\! Этот бот поможет тебе отслеживать время\\, которое ты тратишь на разные задачи\\.\n"
                    "Подробнее о возможнотях бота и work flow по [ссылке](https://telegra\\.ph/Time\\-Tracker\\-\\-\\-bot\\-dlya\\-ucheta\\-vremeni\\-10\\-07)\\.\n"
                    "Готовы начать? Нажми на кнопку 'Приступить'\\!")

    update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode="MarkdownV2")

# Обработка нажатия кнопки Приступить
def handle_star_workflow(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
   # query.answer()
    # user = query.from_user
    # register_user(user.id, user.username)
    if update.message.text == "Приступить":
        user = update.message.from_user
        register_user(user.id, user.username)

    return prompt_project_selection(update, context)

# Функция для создания или выбора проекта
def prompt_project_selection(update: Update, context: CallbackContext) -> int:
    with database_connection() as (conn, cursor):
        # Проверяем, из какого источника пришло сообщение
        if update.message:
            user_id = update.message.from_user.id
        else:
            query = update.callback_query
            user_id = query.from_user.id

        cursor.execute("SELECT project_name FROM projects WHERE user_id=?", (user_id,))
        projects = cursor.fetchall()

    if projects:
        keyboard = [
                       [InlineKeyboardButton(p[0], callback_data=p[0]) for p in projects[i:i + 2]]
                       for i in range(0, len(projects), 2)
                   ] + [[InlineKeyboardButton('Создать новый проект', callback_data='new_project')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            update.message.reply_text('Выберите проект или создайте новый', reply_markup=reply_markup)
        else:
            query.message.reply_text('Выберите проект или создайте новый', reply_markup=reply_markup)
        return SELECTION_PROJECT
    else:
        if update.message:
            update.message.reply_text('У вас еще нет проектов. Введите название нового проекта:')
        else:
            query.message.reply_text('У вас еще нет проектов. Введите название нового проекта:')
        return CREATE_PROJECT

# Обработка создания нового проекта
def handle_project_creation(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    project_name = update.message.text.strip()

    if not project_name:
        update.message.reply_text('Название проекта не может быть пустым. Попробуйте снова.')
        return

    if len(project_name) > 50:  # Adjust the max length as needed
        update.message.reply_text('Название проекта слишком длинное. Максимальная длина - 50 символов.')
        return

    try:
        create_new_project(user_id, project_name)
        update.message.reply_text(f'Проект "{project_name}" создан.')
    except Exception as e:
        update.message.reply_text('Не удалось создать проект. Попробуйте снова.')
        logger.error(f"Error creating project: {e}")

    # Возвращаем бота в обычный режим после создания проекта
    return prompt_project_selection(update, context)

# Обработка выбра проекта
def project_choice_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    if query.data == 'new_project':
        query.edit_message_text(text="Введите название нового проекта:")
        return CREATE_PROJECT
    else:
        project_name = query.data
        user_id = query.from_user.id

        # Ищем project_id по имени проекта
        project_id = get_project_id(user_id, project_name)
        if project_id is None:
            query.edit_message_text(text="Проект не найден, попробуйте снова.")
            return SELECTION_PROJECT

        # Сохраняем project_id в user_data
        context.user_data['selected_project_id'] = project_id

        # Отправляем кнопку для старта времени
        keyboard = [[InlineKeyboardButton('Старт', callback_data='start_time')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text('Начинем?', reply_markup=reply_markup)

        return TRACK_TIME

# выгрузка данных
def handle_export_data(update:Update, context:CallbackContext) -> None:
    user_id = update.message.from_user.id

    #проверка есть ли запущенный таймер
    running_timer = context.user_data.get('start_time')
    if running_timer:
        update.message.reply_text('Таймер запущен. Остановите его пере выгрузкой данных.')

    file_data = export_user_data(user_id)
    if file_data is None:
        update.message.reply_text('Данные отсутствуют.')
        return

    #отправка данных
    update.message.reply_document(document=file_data, filename='TimeTrackingBot.xlsx')

# начало подсчета времени
def start_time_tracking(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    project_id = context.user_data.get('selected_project_id')
    user_id = query.from_user.id

    if project_id is None:
        query.edit_message_text(text="Ошибка: проект не выбран.")
        return ConversationHandler.END

    tracker = TimeTracker()
    tracker.start(time.time())
    context.user_data['time_tracker'] = tracker

    query.edit_message_text("Время пошло!")

    keyboard = [
        [
        InlineKeyboardButton('Пауза', callback_data='pause_time'),
        InlineKeyboardButton('Стоп', callback_data='stop_time')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_reply_markup(reply_markup=reply_markup)
    return TRACK_TIME

# Функция аузы
def pause_time(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    tracker = context.user_data.get('time_tracker')
    if tracker:
        tracker.pause(time.time())

    query.edit_message_text("Время на паузе.")

    keyboard = [
        [
        InlineKeyboardButton('Продолжить', callback_data='resume_time'),
        InlineKeyboardButton('Стоп', callback_data='stop_time')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_reply_markup(reply_markup=reply_markup)

    return TRACK_TIME

# функция для того что бы продолжить время
def resume_time(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    tracker = context.user_data.get('time_tracker')
    if tracker:
        tracker.resume(time.time())

    query.edit_message_text("Время продолжено.")

    keyboard = [
        [
        InlineKeyboardButton('Пауза', callback_data='pause_time'),
        InlineKeyboardButton('Стоп', callback_data='stop_time')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_reply_markup(reply_markup=reply_markup)

    return TRACK_TIME

# остановка, подсчет и запись времени
def stop_time_tracking(update: Update, context: CallbackContext) -> int:
    with database_connection() as (conn, cursor):
        query = update.callback_query
        query.answer()

        user_id = query.from_user.id
        tracker = context.user_data.get('time_tracker')

        if tracker:
            current_time = time.time()
            result = tracker.stop(current_time)
            start_time = result['start_time']
            end_time = result['end_time']
            total_pause_time = result['total_pause_time']
            total_work_time = result['total_work_time']

            # сохраняем время в бд
            project_id = context.user_data.get('selected_project_id')
            cursor.execute(
                "INSERT INTO time_tracking (user_id, project_id, start_time, end_time, total_pause_time, total_work_time) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, project_id, start_time, end_time, total_pause_time, total_work_time)
            )
            conn.commit()

            total_time_min = total_work_time / 60
            query.message.reply_text(f'Время остановлено! Прошло {total_time_min:.1f} минут')
            
            # Additional debug information
            query.message.reply_text(f"Debug info:\nStart: {start_time}\nEnd: {end_time}\nPause: {total_pause_time}\nWork: {total_work_time}")
        else:
            query.message.reply_text('Ошибка: таймер не был запущен.')

        return prompt_project_selection(update, context)

def fallback_handler(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Извините, я не понял вашу команду. Пожалуйста, попробуйте снова.")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Операция отменена.")
    return ConversationHandler.END

def main():
    TOKEN = os.getenv('BOT_TOKEN')

    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Создаем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.text & ~Filters.command, handle_star_workflow)],
        states={
            CREATE_PROJECT: [MessageHandler(Filters.text & ~Filters.command, handle_project_creation)],
            SELECTION_PROJECT: [CallbackQueryHandler(project_choice_callback)],
            TRACK_TIME: [
                CallbackQueryHandler(start_time_tracking, pattern='^start_time$'),
                CallbackQueryHandler(pause_time, pattern='pause_time'),
                CallbackQueryHandler(resume_time, pattern='resume_time'),
                CallbackQueryHandler(stop_time_tracking, pattern='stop_time'),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(Filters.all, fallback_handler)
        ]
    )

    # Обр��ботчики
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(MessageHandler(Filters.regex('^Приступить$'), handle_star_workflow))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Выгрузить данные$'), handle_export_data))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    create_tables()
    main()