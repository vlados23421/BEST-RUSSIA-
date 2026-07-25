import os
import logging
import threading
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- НАСТРОЙКИ БЕЗОПАСНОСТИ И ПОДКЛЮЧЕНИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8957594048:AAEgctfsZve38fv6CwPOXILf3UqI9Gq2WbQ")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "8915047087") 

bot = telebot.TeleBot(BOT_TOKEN)

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (SQLite) ---
DB_FILE = "/tmp/best_russia.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS blacklist (user_id INTEGER PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS apps_archive (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, age TEXT, experience TEXT, status TEXT)''')
    
    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_apps', 0)")
    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('accepted_apps', 0)")
    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('declined_apps', 0)")
    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('recruitment_open', 1)")
    
    conn.commit()
    conn.close()

init_db()

user_applications = {}
admin_states = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def clean_input(text: str) -> str:
    if not text: return ""
    return text.strip()[:500]

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = None
    if fetchone: result = cursor.fetchone()
    elif fetchall: result = cursor.fetchall()
    if commit: conn.commit()
    conn.close()
    return result

def is_banned(user_id):
    res = db_query("SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,), fetchone=True)
    return res is not None

def register_user(user_id, username):
    db_query("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username), commit=True)

# --- Фоновый веб-сервер для Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args): return

def run_health_check():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- ЛОГИКА АДМИН-ПАНЕЛИ ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return

    total_users = db_query("SELECT COUNT(*) FROM users", fetchone=True)
    total_apps = db_query("SELECT value FROM stats WHERE key = 'total_apps'", fetchone=True)
    accepted = db_query("SELECT value FROM stats WHERE key = 'accepted_apps'", fetchone=True)
    is_open = db_query("SELECT value FROM stats WHERE key = 'recruitment_open'", fetchone=True)
    
    status_recruitment = "🟢 ОТКРЫТ" if is_open == 1 else "🔴 ЗАКРЫТ"

    admin_text = (
        "👑 **ПАНЕЛЬ УПРАВЛЕНИЯ BEST RUSSIA** 👑\n\n"
        f"👥 Всего пользователей в боте: `{total_users}`\n"
        f"📊 Всего подано заявок: `{total_apps}` (Одобрено: `{accepted}`)\n"
        f"⚙️ Прием анкет сейчас: **{status_recruitment}**\n\n"
        "Выберите действие на панели ниже:"
    )

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        InlineKeyboardButton("🚫 ЧС / Бан", callback_data="admin_blacklist_menu"),
        InlineKeyboardButton("🔒 Вкл/Выкл Набор", callback_data="admin_toggle_recruitment"),
        InlineKeyboardButton("💾 Скачать Архив", callback_data="admin_download_db")
    )
    bot.send_message(message.chat.id, admin_text, parse_mode="Markdown", reply_markup=markup)

# --- ЛОГИКА ПОЛЬЗОВАТЕЛЕЙ ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if is_banned(message.from_user.id): return
    register_user(message.from_user.id, message.from_user.username)

    welcome_text = (
        "✨ **Добро пожаловать в систему подачи заявок проекта BEST RUSSIA!** ✨\n\n"
        "Выберите интересующую вас вакансию ниже, чтобы начать заполнение анкеты."
    )
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("Подать на Хелпера 📝"))
    markup.add(KeyboardButton("Подать на Агента Discord 🛠️"))
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in ["Подать на Хелпера 📝", "Подать на Агента Discord 🛠️"])
def start_application(message):
    user_id = message.from_user.id
    if is_banned(user_id): return

    is_open = db_query("SELECT value FROM stats WHERE key = 'recruitment_open'", fetchone=True)
    if is_open == 0:
        bot.send_message(message.chat.id, "🔒 **Извините, но в данный момент прием заявок временно закрыт администрацией проекта.**", parse_mode="Markdown")
        return
    
    chosen_role = "Хелпер" if "Хелпера" in message.text else "Агент поддержки Discord"
    min_age = 12 if chosen_role == "Хелпер" else 15
    
    user_applications[user_id] = {
        "username": f"@{message.from_user.username}" if message.from_user.username else "Скрыт/Нету",
        "user_id": user_id,
        "role": chosen_role,
        "min_age": min_age
    }
    
    bot.send_message(message.chat.id, f"Вы выбрали: **{chosen_role}**.\n\nШаг 1. Укажите ваш **реальный возраст** (цифрой, минимум {min_age} лет):", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    bot.register_next_step_handler(message, process_age)

def process_age(message):
    user_id = message.from_user.id
    if user_id not in user_applications: return
        
    text = clean_input(message.text)
    min_role_age = user_applications[user_id]["min_age"]
    
    if not text.isdigit() or not (min_role_age <= int(text) <= 60):
        bot.send_message(message.chat.id, f"⚠️ Недостаточный возраст или неверный формат. Требуется возраст от {min_role_age} до 60 лет. Повторите ввод:")
        bot.register_next_step_handler(message, process_age)
        return

    user_applications[user_id]["age"] = text
    bot.send_message(message.chat.id, "Шаг 2. Расскажите о вашем **опыте работы** на аналогичных проектах/серверах (минимум 10 символов):", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_experience)

def process_experience(message):
    user_id = message.from_user.id
    if user_id not in user_applications: return

    text = clean_input(message.text)
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

    user_applications[user_id]["time"] = clean_input(message.text)
    data = user_applications[user_id]
    
    summary = (
        "📋 **Проверьте ваши данные перед отправкой:**\n\n"
        f"• **Должность:** {data['role']}\n"
        f"• **Возраст:** {data['age']}\n"
        f"• **Опыт:** {data['experience']}\n"
        f"• **Время онлайн:** {data['time']}\n\n"
        "Все верно?"
    )
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
        db_query("INSERT INTO apps_archive (user_id, role, age, experience, status) VALUES (?, ?, ?, ?, 'На рассмотрении')", 
                 (data['user_id'], data['role'], data['age'], data['experience']), commit=True)

        emoji = "🚀" if data['role'] == "Хелпер" else "🎮"
        admin_message = (
            f"{emoji} **НОВАЯ ЗАЯВКА | {data['role'].upper()}** {emoji}\n\n"
            f"👤 **Кандидат:** {data['username']} (ID: `{data['user_id']}`)\n"
            f"🔞 **Возраст:** {data['age']}\n"
            f"🕒 **Готов уделять:** {data['time']}\n"
            f"💼 **Опыт работы:**\n{data['experience']}\n"
        )
        
        inline_markup = InlineKeyboardMarkup()
        inline_markup.row(
            InlineKeyboardButton("Одобрить ✅", callback_data=f"accept_{data['user_id']}_app"),
            InlineKeyboardButton("Отклонить ❌", callback_data=f"decline_{data['user_id']}_app")
        )
        inline_markup.row(InlineKeyboardButton("🛑 Забанить спамера", callback_data=f"ban_{data['user_id']}"))
        
        bot.send_message(ADMIN_CHAT_ID, admin_message, parse_mode="Markdown", reply_markup=inline_markup)
