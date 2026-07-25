import os
import logging
import threading
import sqlite3
from flask import Flask
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN", "8957594048:AAEgctfsZve38fv6CwPOXILf3UqI9Gq2WbQ")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "8915047087")

bot = telebot.TeleBot(BOT_TOKEN)
DB_FILE = ":memory:"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS blacklist (user_id INTEGER PRIMARY KEY)')
    cursor.execute('CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)')
    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_apps', 0)")
    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('accepted_apps', 0)")
    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('recruitment_open', 1)")
    conn.commit()
    conn.close()

init_db()
user_applications = {}
admin_states = {}

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = cursor.fetchone() if fetchone else (cursor.fetchall() if fetchall else None)
    if commit: conn.commit()
    conn.close()
    return result

app = Flask(__name__)
@app.route('/')
def home(): return "Бот BEST RUSSIA активен!", 200

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID): return
    total_users = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    total_apps = db_query("SELECT value FROM stats WHERE key = 'total_apps'", fetchone=True)[0]
    accepted = db_query("SELECT value FROM stats WHERE key = 'accepted_apps'", fetchone=True)[0]
    is_open = db_query("SELECT value FROM stats WHERE key = 'recruitment_open'", fetchone=True)[0]
    status_recruitment = "🟢 ОТКРЫТ" if is_open == 1 else "🔴 ЗАКРЫТ"
    
    admin_text = f"👑 **ПАНЕЛЬ УПРАВЛЕНИЯ BEST RUSSIA** 👑\n\n👥 Пользователей в боте: `{total_users}`\n📊 Подано заявок: `{total_apps}` (Одобрено: `{accepted}`)\n⚙️ Прием анкет сейчас: **{status_recruitment}**"
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"), InlineKeyboardButton("🚫 ЧС / Бан", callback_data="admin_blacklist_menu"), InlineKeyboardButton("🔒 Вкл/Выкл Набор", callback_data="admin_toggle_recruitment"), InlineKeyboardButton("💾 Скачать Архив", callback_data="admin_download_db"))
    bot.send_message(message.chat.id, admin_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    is_banned = db_query("SELECT 1 FROM blacklist WHERE user_id = ?", (message.from_user.id,), fetchone=True)
    if is_banned: return
    db_query("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (message.from_user.id, message.from_user.username), commit=True)
    
    welcome_text = "✨ **Добро пожаловать в систему подачи заявок проекта BEST RUSSIA!** ✨\n\nВыберите интересующую вас вакансию ниже."
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("Подать на Хелпера 📝"), KeyboardButton("Подать на Агента Discord 🛠️"))
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in ["Подать на Хелпера 📝", "Подать на Агента Discord 🛠️"])
def start_application(message):
    is_banned = db_query("SELECT 1 FROM blacklist WHERE user_id = ?", (message.from_user.id,), fetchone=True)
    if is_banned: return
    is_open = db_query("SELECT value FROM stats WHERE key = 'recruitment_open'", fetchone=True)[0]
    if is_open == 0:
        bot.send_message(message.chat.id, "🔒 **Извините, сейчас прием заявок временно закрыт администрацией.**", parse_mode="Markdown")
        return
    chosen_role = "Хелпер" if "Хелпера" in message.text else "Агент поддержки Discord"
    min_age = 12 if chosen_role == "Хелпер" else 15
    user_applications[message.from_user.id] = {"username": f"@{message.from_user.username}" if message.from_user.username else "Скрыт", "user_id": message.from_user.id, "role": chosen_role, "min_age": min_age}
    bot.send_message(message.chat.id, f"Вы выбрали: **{chosen_role}**.\n\nШаг 1. Укажите ваш **реальный возраст** (цифрой, минимум {min_age} лет):", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    bot.register_next_step_handler(message, process_age)

def process_age(message):
    user_id = message.from_user.id
    if user_id not in user_applications: return
    text = message.text.strip() if message.text else ""
    min_role_age = user_applications[user_id]["min_age"]
    if not text.isdigit() or not (min_role_age <= int(text) <= 60):
        bot.send_message(message.chat.id, f"⚠️ Требуется возраст цифрами от {min_role_age} до 60 лет. Повторите ввод:")
        bot.register_next_step_handler(message, process_age)
        return
    user_applications[user_id]["age"] = text
    bot.send_message(message.chat.id, "Шаг 2. Расскажите о вашем **опыте работы** на аналогичных проектах (минимум 10 символов):", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_experience)

def process_experience(message):
    user_id = message.from_user.id
    if user_id not in user_applications: return
    text = message.text.strip() if message.text else ""
    if len(text) < 10:
        bot.send_message(message.chat.id, "⚠️ Опишите ваш опыт подробнее (минимум 10 символов):")
        bot.register_next_step_handler(message, process_experience)
        return
    user_applications[user_id]["experience"] = text
    bot.send_message(message.chat.id, "Шаг 3. Сколько **времени (в часах)** вы готовы уделять проекту ежедневно?", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_time)

def process_time(message):
    user_id = message.from_user.id
    if user_id not in user_applications: return
    user_applications[user_id]["time"] = message.text.strip() if message.text else ""
    data = user_applications[user_id]
    summary = f"📋 **Проверьте ваши данные:**\n\n• **Должность:** {data['role']}\n• **Возраст:** {data['age']}\n• **Опыт:** {data['experience']}\n• **Время онлайн:** {data['time']}\n\nВсе верно?"
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("Отправить заявку ✅"), KeyboardButton("Отменить ❌"))
    bot.send_message(message.chat.id, summary, parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(message, process_final)

def process_final(message):
    user_id = message.from_user.id
    if user_id not in user_applications: return
    if message.text == "Отправить заявку ✅":
        data = user_applications[user_id]
        db_query("UPDATE stats SET value = value + 1 WHERE key = 'total_apps'", commit=True)
        emoji = "🚀" if data['role'] == "Хелпер" else "🎮"
        admin_message = f"{emoji} **НОВАЯ ЗАЯВКА | {data['role'].upper()}** {emoji}\n\n👤 **Кандидат:** {data['username']} (ID: `{data['user_id']}`)\n🔞 **Возраст:** {data['age']}\n🕒 **Готов уделять:** {data['time']}\n💼 **Опыт работы:**\n{data['experience']}"
        inline_markup = InlineKeyboardMarkup()
        inline_markup.row(InlineKeyboardButton("Одобрить ✅", callback_data=f"accept_{data['user_id']}"), InlineKeyboardButton("Отклонить ❌", callback_data=f"decline_{data['user_id']}"))
        inline_markup.row(InlineKeyboardButton("🛑 Забанить спамера", callback_data=f"ban_{data['user_id']}"))
        bot.send_message(ADMIN_CHAT_ID, admin_message, parse_mode="Markdown", reply_markup=inline_markup)
        bot.send_message(message.chat.id, "🎉 **Ваша заявка успешно отправлена!**", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    else:
        bot.send_message(message.chat.id, "❌ Заполнение отменено.", reply_markup=ReplyKeyboardRemove())
    user_applications.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if str(call.message.chat.id) != str(ADMIN_CHAT_ID): return
    if call.data.startswith('accept_') or call.data.startswith('decline_'):
        action, target_user_id = call.data.split('_')
        if action == "accept":
            status_text = "🟢 ОДОБРЕНО АДМИНИСТРАЦИЕЙ"
            user_notification = "🎉 **Поздравляем! Ваша заявка одобрена.** С вами скоро свяжутся."
            db_query("UPDATE stats SET value = value + 1 WHERE key = 'accepted_apps'", commit=True)
        else:
            status_text = "🔴 ОТКЛОНЕНО АДМИНИСТРАЦИЕЙ"
            user_notification = "❌ **К сожалению, ваша заявка была отклонена.**"
        try: bot.send_message(target_user_id, user_notification, parse_mode="Markdown")
        except Exception: pass
        bot.edit_message_text(chat_id=ADMIN_CHAT_ID, message_id=call.message.message_id, text=call.message.text + f"\n\n👉 **Решение:** {status_text}", reply_markup=None)
    elif call.data.startswith('ban_'):
        target_id = call.data.split('_')[1]
        db_query("INSERT OR IGNORE INTO blacklist (user_id) VALUES (?)", (target_id,), commit=True)
        bot.answer_callback_query(call.id, "Пользователь забанен!", show_alert=True)
        bot.edit_message_reply_markup(chat_id=ADMIN_CHAT_ID, message_id=call.message.message_id, reply_markup=None)
    elif call.data == "admin_broadcast":
        bot.send_message(ADMIN_CHAT_ID, "📢 Введите текст для массовой рассылки всем (или напишите 'отмена'):")
