import telebot
from telebot import types
import sqlite3
import random
from threading import Thread
from flask import Flask

# 1. ВСТАВЬ СВОЙ ТОКЕН СЮДА
TOKEN = '8410401702:AAFqDRb8cCKAY7gj5NCZmZ06hGUIfk4cP04'
bot = telebot.TeleBot(TOKEN)


URL_SERVER = 'https://onrender.com'


# --- МИКРО-СЕРВЕР ДЛЯ ОБХОДА ЗАСЫПАНИЯ RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Сервер активен, бот защищен от засыпания!"

def run_flask():
    # Запуск веб-сервера на порту 10000, который требует бесплатный Render
    app.run(host='0.0.0.0', port=10000)

# Хранилище состояний пользователей
user_states = {}

def query_db(sql, params=()):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(sql, params)
    results = cursor.fetchall()
    conn.close()
    return results

# Безопасное удаление старого сообщения
def safe_delete(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass

# --- ИНТЕРФЕЙС И ЛОГИКА ---

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
        "Давай подберем идеальный маршрут. "
        "Выбери формат прогулки ниже: 👇"
    )
    bot.send_message(chat_id, welcome_text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('format_'))
def handle_format(call):
    chat_id = call.message.chat.id
    user_states[chat_id]['is_culture'] = 1 if call.data == "format_culture" else 0
    
    # Удаляем самое первое приветственное сообщение, чтобы было компактно
    safe_delete(chat_id, call.message.message_id)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_free = types.InlineKeyboardButton("🆓 Только бесплатные места", callback_data="budget_free")
    btn_paid = types.InlineKeyboardButton("💳 Готов к платным локациям", callback_data="budget_paid")
    markup.add(btn_free, btn_paid)
    
    # Отправляем второй вопрос новым чистым сообщением
    msg = bot.send_message(
        chat_id, 
        "<b>Отличный выбор!</b> 🎯\n\nТеперь определимся с бюджетом твоей прогулки:", 
        parse_mode='HTML', 
        reply_markup=markup
    )
    user_states[chat_id]['last_msg_id'] = msg.message_id

@bot.callback_query_handler(func=lambda call: call.data.startswith('budget_'))
def handle_budget(call):
    chat_id = call.message.chat.id
    user_states[chat_id]['search_paid'] = 1 if call.data == "budget_paid" else 0
    
    # Удаляем сообщение со вторым вопросом
    if 'last_msg_id' in user_states[chat_id]:
        safe_delete(chat_id, user_states[chat_id]['last_msg_id'])
    safe_delete(chat_id, call.message.message_id)
    
    send_location(chat_id)

def send_location(chat_id):
    is_culture = user_states[chat_id]['is_culture']
    is_paid = user_states[chat_id]['search_paid']
    
    # Запрос всех полей из расширенной БД
    sql = "SELECT name, description, cafe_hint, map_url FROM locations WHERE is_culture = ? AND is_paid = ?"
    results = query_db(sql, (is_culture, is_paid))
    
    if results:
        name, desc, cafe, map_url = random.choice(results)
        
        # Создаем Inline-кнопки под карточкой
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # Кнопка со ссылкой на Яндекс.Карты (интеграция маршрута)
        if map_url:
            btn_map = types.InlineKeyboardButton("🗺️ Смотреть маршрут на карте", url=map_url)
            markup.add(btn_map)
            
        btn_retry = types.InlineKeyboardButton("🔄 Мне не нравится, давай другое", callback_data="action_retry")
        btn_restart = types.InlineKeyboardButton("🏁 Начать сначала", callback_data="action_restart")
        markup.add(btn_retry, btn_restart)
        
        # Формируем красивый текст карточки
        output_text = f"📍 <b>{name}</b>\n\n"
        output_text += f"📝 <i>Описание:</i> {desc}\n\n"
        
        # Если есть подсказка по кафе (только для платных) — выводим её
        if cafe:
            output_text += f"{cafe}\n\n"
            
        output_text += "Вы можете изучить маршрут на карте или обновить выбор. 👇"
        
        # Отправляем карточку новым чистым сообщением
        msg = bot.send_message(chat_id, output_text, parse_mode='HTML', reply_markup=markup)
        user_states[chat_id]['last_card_id'] = msg.message_id
    else:
        bot.send_message(chat_id, "❌ Ошибка: Локации не найдены.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('action_'))
def handle_actions(call):
    chat_id = call.message.chat.id
    
    # При любых действиях удаляем старую карточку, чтобы не спамить экран
    if 'last_card_id' in user_states[chat_id]:
        safe_delete(chat_id, user_states[chat_id]['last_card_id'])
    safe_delete(chat_id, call.message.message_id)
        
    if call.data == "action_retry":
        if chat_id in user_states and 'is_culture' in user_states[chat_id]:
            send_location(chat_id)
        else:
            start_cmd(call.message)
    elif call.data == "action_restart":
        start_cmd(call.message)

# --- ИНТЕГРАЦИЯ ПОТОКОВ ДЛЯ RENDER ---
if __name__ == '__main__':
    # Запускаем Flask в отдельном параллельном потоке, чтобы он слушал порт 10000
    Thread(target=run_flask).start()
    
    print("Робот-гид успешно запущен, защищен от засыпания на Render и слушает базу...")
    bot.infinity_polling()
