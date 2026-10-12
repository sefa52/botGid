import telebot
from telebot import types
import sqlite3
import random

TOKEN = '8410401702:AAFqDRb8cCKAY7gj5NCZmZ06hGUIfk4cP04'
bot = telebot.TeleBot(TOKEN)

# Хранилище состояний пользователей в оперативной памяти
user_states = {}

# Функция для безопасного подключения к внешней физической БД
def query_db(sql, params=()):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(sql, params)
    results = cursor.fetchall()
    conn.close()
    return results

# --- ИНТЕРФЕЙС И ЛОГИКА ОПРОСА ---

@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    user_states[chat_id] = {}
    
   
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_street = types.InlineKeyboardButton("🌳 Открытые пространства (Улица)", callback_data="format_street")
    btn_culture = types.InlineKeyboardButton("🏛️ Крытые помещения (Музеи/Выставки)", callback_data="format_culture")
    markup.add(btn_street, btn_culture)
    
    welcome_text = (
        "<b>Приветствуем в туристическом гиде по Санкт-Петербургу!</b> ✨\n\n"
        "Давай подберем идеальный маршрут под твои цели. "
        "Для начала выбери формат прогулки ниже: 👇"
    )
    bot.send_message(chat_id, welcome_text, parse_mode='HTML', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('format_'))
def handle_format(call):
    chat_id = call.message.chat.id
    user_states[chat_id]['is_culture'] = 1 if call.data == "format_culture" else 0
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_free = types.InlineKeyboardButton(" Только бесплатные места", callback_data="budget_free")
    btn_paid = types.InlineKeyboardButton(" Готов к платным локациям", callback_data="budget_paid")
    markup.add(btn_free, btn_paid)
    
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="<b>Отличный выбор!</b> \n\nТеперь определимся с бюджетом прогулки:",
        parse_mode='HTML',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('budget_'))
def handle_budget(call):
    chat_id = call.message.chat.id
    user_states[chat_id]['is_paid'] = 1 if call.data == "budget_paid" else 0
    
    send_location(chat_id, call.message.message_id)


def send_location(chat_id, message_id):
    is_culture = user_states[chat_id]['is_culture']
    is_paid = user_states[chat_id]['is_paid']
    
    # Чистый SQL-запрос к внешнему файлу database.db
    sql = "SELECT name FROM locations WHERE is_culture = ? AND is_paid = ?"
    results = query_db(sql, (is_culture, is_paid))
    
    if results:
        # Настоящий случайный выбор из отфильтрованного списка БД
        location = random.choice(results)[0]
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_retry = types.InlineKeyboardButton("🔄 Мне не нравится, давай другое", callback_data="action_retry")
        btn_restart = types.InlineKeyboardButton(" Начать сначала", callback_data="action_restart")
        markup.add(btn_retry, btn_restart)
        
        output_text = (
            "📍 <b>Наша рекомендация по вашим критериям:</b>\n\n"
            f"{location}\n\n"
            "Вы можете изучить это место или обновить маршрут. 👇"
        )
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=output_text,
            parse_mode='HTML',
            reply_markup=markup
        )
    else:
        bot.send_message(chat_id, "❌ Ошибка: В базе данных не найдены подходящие локации.")

# Обработка кнопок перегенерации и перезапуска
@bot.callback_query_handler(func=lambda call: call.data.startswith('action_'))
def handle_actions(call):
    chat_id = call.message.chat.id
    if call.data == "action_retry":
        if chat_id in user_states and 'is_culture' in user_states[chat_id]:
            send_location(chat_id, call.message.message_id)
        else:
            start_cmd(call.message)
    elif call.data == "action_restart":
        start_cmd(call.message)

print("Робот-гид успешно запущен, подключен к файлу database.db и слушает запросы...")
bot.infinity_polling()
