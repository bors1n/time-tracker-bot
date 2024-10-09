import sqlite3
import time
import warnings
from importlib.metadata import entry_points

from anyio import current_time

from setup_db import create_tables
from export_data import export_user_data
from connect_to_database import  connect_to_database
from oauthlib.uri_validate import query, userinfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, ConversationHandler, MessageHandler, Filters
from settings import TG_TOKEN

warnings.filterwarnings("ignore")

# Определяем состояния для ConversationHandler
CREATE_PROJECT, SELECTION_PROJECT, TRACK_TIME = range(3)

# Функция для регистрации пользователей
def register_user(user_id, username):
    conn, cursor = connect_to_database()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

# Создания нового проекта
def create_new_project(user_id, project_name):
    conn, cursor = connect_to_database()
    cursor.execute("INSERT INTO projects (user_id, project_name) VALUES (?, ?)", (user_id, project_name))
    conn.commit()
    conn.close()

# Получение id проекта
def get_project_id(user_id, project_name):
    conn, cursor = connect_to_database()
    cursor.execute("SELECT project_id FROM projects WHERE user_id=? AND project_name=?", (user_id, project_name))
    return cursor.fetchone()[0]

# Фукнция для отправки кнопки Start при запуске бота
def start(update: Update, context: CallbackContext) -> None:
    keyboard = [[KeyboardButton("Приступить")],
                [KeyboardButton("Выгрузить данные")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    message_text = ("Привет\\! Этот бот поможет тебе отслеживать время\\, которое ты тратишь на разные задачи\\.\n"
                    "Подробнее о возможностях бота и work flow по [ссылке](https://telegra\\.ph/Time\\-Tracker\\-\\-\\-bot\\-dlya\\-ucheta\\-vremeni\\-10\\-07)\\.\n"
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

    conn, cursor = connect_to_database()
    # Проверяем, из какого источника пришло сообщение
    if update.message:
        user_id = update.message.from_user.id
    else:
        query = update.callback_query
        user_id = query.from_user.id

    cursor.execute("SELECT project_name FROM projects WHERE user_id=?", (user_id,))
    projects = cursor.fetchall()
    conn.close()
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
    project_name = update.message.text

    try:
        create_new_project(user_id, project_name)
        update.message.reply_text(f'Проект "{project_name}" создан.')
    except Exception as e:
        update.message.reply_text('Не удалось создать проект. Попробуйте снова.')

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
        query.edit_message_text('Начинаем?', reply_markup=reply_markup)

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

    # Получаем сохранённый project_id
    project_id = context.user_data.get('selected_project_id')
    user_id = query.from_user.id

    if project_id is None:
        query.edit_message_text(text="Ошибка: проект не выбран.")
        return ConversationHandler.END

    # Фиксируем текущее время как начало отсчета
    start_time = time.time()

    context.user_data['start_time'] = start_time
    context.user_data['start_pause_time'] = start_time
    context.user_data['total_pause_time'] = 0 # тут будем накапливать время в режиме "пауза"
    context.user_data['is_paused'] = False # флаг для отслеживания пауз

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

# Функция паузы
def pause_time(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if context.user_data['is_paused']:
        query.edit_message_text("Отсчет уже на паузе.")
        return TRACK_TIME

    current_time = time.time()
    start_pause_time = context.user_data.get('start_pause_time', 0)
    total_pause_time = context.user_data.get('total_pause_time', 0)

    # добавляем время пузы
    total_pause_time += (current_time - start_pause_time)
    context.user_data['total_pause_time'] = total_pause_time
    context.user_data['is_paused'] = True

    # кнопки для продолжения или остановки
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

    if not context.user_data['is_paused']:
        query.edit_message_text("Отсчет не на паузе.")
        return TRACK_TIME

    start_pause_time = time.time()
    context.user_data['start_pause_time'] = start_pause_time
    context.user_data['is_paused'] = False #обновляем флаг паузы

    # кнопки для паузы или остановки
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
    conn, cursor = connect_to_database()
    query = update.callback_query
    query.answer()

    # получаем данные о времени
    user_id = query.from_user.id
    start_time = context.user_data.get('start_time', 0)
    total_pause_time = context.user_data.get('total_pause_time', 0)
    is_paused = context.user_data.get('is_paused', False)
    start_pause_time = context.user_data.get('start_pause_time', 0)

    if start_time is not None:
        if is_paused:
            # Если таймер на паузе, используем время начала паузы как конечное время
            end_time = start_pause_time
        else:
            end_time = time.time()
        total_work_time = (end_time - start_time)#общее рабочее время

        if not is_paused:
            total_work_time -= total_pause_time # вычитаем время паузы только если таймер не на паузе

        # сохраняем время в бд
        project_id = context.user_data.get('selected_project_id')
        cursor.execute(
            "INSERT INTO time_tracking (user_id, project_id, start_time, end_time, total_pause_time, total_work_time) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, project_id, start_time, end_time, total_pause_time, total_work_time)
        )
        conn.commit()
        conn.close()

        total_time_min = total_work_time / 60
        query.message.reply_text(f'Время остановлено! Прошло {total_time_min:.1f} минут')

        return prompt_project_selection(update, context)
    else:
        query.message.reply_text('Отсчет времени не был запущен')
        return  ConversationHandler.END

def main():
    TOKEN = TG_TOKEN

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
        fallbacks=[]
    )

    # Обработчики
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(MessageHandler(Filters.regex('^Приступить$'), handle_star_workflow))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Выгрузить данные$'), handle_export_data))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    create_tables()
    main()

