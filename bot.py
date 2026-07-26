import os
import threading
from flask import Flask
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN", "8957594048:AAFpWXMuYMzqdW89S1m8BKvkePN8TcQKOw0")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "8915047087")
AGE_HELPER = 12
AGE_DISCORD = 15

# Логирование
import logging
logging.basicConfig(level=logging.INFO)

bot = telebot.TeleBot(BOT_TOKEN)

# Временные переменные
active_users = set()
recruitment_open = True
user_applications = {}
admin_states = {}

# Flask для Heartbeat сервера
app = Flask(__name__)
@app.route('/')
def home():
    return "Бот BEST RUSSIA онлайн!", 200

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Главное меню ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    active_users.add(message.from_user.id)
    welcome_text = (
        "✨ **Добро пожаловать в систему подачи заявок проекта BEST RUSSIA!** ✨\n\n"
        "Выберите интересующую вас вакансию или посмотрите требования ниже."
    )
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row(KeyboardButton("Подать на Хелпера 📝"))
    markup.row(KeyboardButton("Подать на Агента Discord 🛠️"))
    markup.row(KeyboardButton("Требования к кандидатам"))
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# --- Обработка кнопки "Требования" ---
@bot.message_handler(func=lambda msg: msg.text == "Требования к кандидатам")
def show_requirements_menu(message):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Хелпер 📝", callback_data="requirements_helper"),
        InlineKeyboardButton("Агент Discord 🛠️", callback_data="requirements_discord")
    )
    bot.send_message(message.chat.id, "Выберите роль, чтобы ознакомиться с требованиями:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('requirements_'))
def handle_requirements(call):
    if call.data == 'requirements_helper':
        text = (
            "📝 **Требования к Хелперу:**\n"
            f"- Возраст: минимум {AGE_HELPER} лет.\n"
            "- Опыт работы с проектами.\n"
            "- Ответственность и коммуникабельность.\n"
            "- Активный пользователь, дружелюбный, отзывчивый."
        )
        bot.send_message(call.message.chat.id, text)
    elif call.data == 'requirements_discord':
        text = (
            "📝 **Требования к Агенту поддержки Discord:**\n"
            f"- Возраст: минимум {AGE_DISCORD} лет.\n"
            "- Знание Discord и его функций.\n"
            "- Хорошие коммуникативные навыки.\n"
            "- Готовность помогать другим пользователям.\n"
            "✅ Ответственный, дружелюбный и терпеливый."
        )
        bot.send_message(call.message.chat.id, text)

# --- Обработка подачи заявки ---
@bot.message_handler(func=lambda msg: msg.text in ["Подать на Хелпера 📝", "Подать на Агента Discord 🛠️"])
def start_application(message):
    global recruitment_open
    if not recruitment_open:
        bot.send_message(message.chat.id, "🔒 **Извините, сейчас прием заявок закрыт.**", parse_mode="Markdown")
        return
    chosen_role = "Хелпер" if "Хелпера" in message.text else "Агент поддержки Discord"
    min_age = AGE_HELPER if chosen_role == "Хелпер" else AGE_DISCORD
    user_applications[message.from_user.id] = {
        "username": f"@{message.from_user.username}" if message.from_user.username else "Скрыт",
        "user_id": message.from_user.id,
        "role": chosen_role,
        "min_age": min_age
    }
    bot.send_message(
        message.chat.id,
        f"Вы выбрали: **{chosen_role}**.\n\nШаг 1. Укажите ваш *реальный возраст* (минимум {min_age} лет):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, process_age)

def process_age(message):
    user_id = message.from_user.id
    if user_id not in user_applications:
        return
    try:
        age_val = int(message.text.strip())
    except:
        bot.send_message(message.chat.id, f"⚠️ Введите числовой возраст от {user_applications[user_id]['min_age']} до 60.")
        bot.register_next_step_handler(message, process_age)
        return
    if age_val < user_applications[user_id]['min_age'] or age_val > 60:
        bot.send_message(message.chat.id, f"⚠️ Возраст должен быть от {user_applications[user_id]['min_age']} до 60.")
        bot.register_next_step_handler(message, process_age)
        return
    user_applications[user_id]["age"] = str(age_val)
    bot.send_message(
        message.chat.id,
        "Шаг 2. Расскажите о вашем опыте работы на подобных проектах (минимум 10 символов):",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, process_experience)

def process_experience(message):
    user_id = message.from_user.id
    if user_id not in user_applications:
        return
    text = message.text.strip()
    if len(text) < 10:
        bot.send_message(message.chat.id, "⚠️ Опишите подробнее (минимум 10 символов):")
        bot.register_next_step_handler(message, process_experience)
        return
    user_applications[user_id]["experience"] = text
    bot.send_message(
        message.chat.id,
        "Шаг 3. Сколько часов в день готовы уделять проекту?",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, process_time)

def process_time(message):
    user_id = message.from_user.id
    if user_id not in user_applications:
        return
    text = message.text.strip()
    user_applications[user_id]["time"] = text
    data = user_applications[user_id]
    summary = (
        f"📋 **Проверьте ваши данные:**\n\n"
        f"• **Должность:** {data['role']}\n"
        f"• **Возраст:** {data['age']}\n"
        f"• **Опыт:** {data['experience']}\n"
        f"• **Время:** {data['time']}\n\n"
        "Все верно?"
    )
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("Отправить заявку ✅"), KeyboardButton("Отменить ❌"))
    bot.send_message(message.chat.id, summary, parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(message, process_final)

def process_final(message):
    user_id = message.from_user.id
    if user_id not in user_applications:
        return
    if message.text == "Отправить заявку ✅":
        data = user_applications[user_id]
        emoji = "🚀" if data['role'] == "Хелпер" else "🎮"
        admin_msg = (
            f"{emoji} **НОВАЯ ЗАЯВКА | {data['role'].upper()}** {emoji}\n\n"
            f"👤 **Кандидат:** {data['username']} (ID: `{data['user_id']}`)\n"
            f"🔞 **Возраст:** {data['age']}\n"
            f"🕒 **Готовность уделять:** {data['time']}\n"
            f"💼 **Опыт работы:**\n{data['experience']}"
        )
        inline_kb = InlineKeyboardMarkup()
        inline_kb.row(
            InlineKeyboardButton("Одобрить ✅", callback_data=f"accept_{data['user_id']}"),
            InlineKeyboardButton("Отклонить ❌", callback_data=f"decline_{data['user_id']}")
        )
        bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="Markdown", reply_markup=inline_kb)
        bot.send_message(
            message.chat.id,
            "🎉 **Ваша заявка отправлена!** Наши админы рассмотрят её в ближайшее время.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        bot.send_message(message.chat.id, "❌ Заполнение отменено.", reply_markup=ReplyKeyboardRemove())

    user_applications.pop(user_id, None)

# --- Обработка решений админов ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_') or call.data.startswith('decline_'))
def handle_decision(call):
    if str(call.message.chat.id) != str(ADMIN_CHAT_ID):
        return
    action, user_id_str = call.data.split('_')
    user_id = int(user_id_str)
    if action == "accept":
        text = "🟢 ОДОБРЕНА"
        notification = "🎉 Ваша заявка одобрена!"
    else:
        text = "🔴 ОТКЛОНЕНА"
        notification = "❌ Ваша заявка отклонена"
    try:
        bot.send_message(user_id, notification, parse_mode="Markdown")
    except:
        pass
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=call.message.text + f"\n\n👉 **Решение:** {text}",
        reply_markup=None
    )

# --- Команда или обработка /admin ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return
    status = "🟢 ОТКРЫТ" if recruitment_open else "🔴 ЗАКРЫТ"
    text = (
        "👑 **Панель управления** 👑\n\n"
        f"Пользователей для рассылки: {len(active_users)}\n"
        f"Прием заявок: **{status}**\n"
        f"Возраст - Хелпер: [{AGE_HELPER}+], Discord: [{AGE_DISCORD}+]\n\n"
        "Выберите действие ниже:"
    )
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        InlineKeyboardButton("🔒 Вкл/Выкл Набор", callback_data="admin_toggle_recruitment")
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

# --- Обработка Callback для админ панелий ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    global recruitment_open
    # Для админ панели
    if str(call.message.chat.id) == str(ADMIN_CHAT_ID):
        if call.data == "admin_broadcast":
            bot.send_message(ADMIN_CHAT_ID, "Введите текст рассылки или 'отмена':")
            admin_states[ADMIN_CHAT_ID] = "broadcast"
        elif call.data == "admin_toggle_recruitment":
            recruitment_open = not recruitment_open
            state_str = "🟢 ОТКРЫТ" if recruitment_open else "🔴 ЗАКРЫТ"
            bot.answer_callback_query(call.id, f"Статус набора: {state_str}", show_alert=True)
            # Обновить панель
            admin_panel(call.message)
        return

    # Для решений заявок
    if call.data.startswith('accept_') or call.data.startswith('decline_'):
        handle_decision(call)

# --- Обработка сообщений для рассылки ---
@bot.message_handler(func=lambda msg: str(msg.chat.id) == str(ADMIN_CHAT_ID) and admin_states.get(msg.chat.id)=='broadcast')
def handle_broadcast(message):
    if message.text.lower() == "отмена":
        bot.send_message(ADMIN_CHAT_ID, "Рассылка отменена.")
        admin_states.pop(ADMIN_CHAT_ID, None)
        return
    count = 0
    for u in active_users:
        try:
            bot.send_message(u, message.text, parse_mode="Markdown")
            count += 1
        except:
            pass
    bot.send_message(ADMIN_CHAT_ID, f"Рассылка завершена! Открыто: {count} пользователей.")
    admin_states.pop(ADMIN_CHAT_ID, None)

# Запуск
if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
