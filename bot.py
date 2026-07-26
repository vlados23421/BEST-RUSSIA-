import os
import threading
from flask import Flask
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN", "8957594048:AAFpWXMuYMzqdW89S1m8BKvkePN8TcQKOw0")  # Замените или настройте переменные
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "8915047087")
AGE_HELPER = 12
AGE_DISCORD = 15

# Инициализация
bot = telebot.TeleBot(BOT_TOKEN)

# Временные данные
active_users = set()
recruitment_open = True
user_applications = {}
admin_states = {}

# Flask для heartbeat
app = Flask(__name__)
@app.route('/')
def home():
    return "Бот BEST RUSSIA онлайн!", 200

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Обработчик /start /help ---
@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    # Добавляем пользователя в активных
    active_users.add(message.from_user.id)
    # Отправляем меню
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.row(KeyboardButton("Подать на Хелпера 📝"))
    keyboard.row(KeyboardButton("Подать на Агента Discord 🛠️"))
    keyboard.row(KeyboardButton("Требования к кандидатам"))

    bot.send_message(
        message.chat.id,
        "✨ **Добро пожаловать!** \nВыберите вакансию или посмотрите требования.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# --- Обработка кнопки "Требования" ---
@bot.message_handler(func=lambda m: m.text == "Требования к кандидатам")
def show_requirements_menu(message):
    # Создаем inline меню для выбора роли
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Хелпер 📝", callback_data="requirements_helper"),
        InlineKeyboardButton("Агент Discord 🛠️", callback_data="requirements_discord")
    )
    bot.send_message(
        message.chat.id,
        "Выберите роль, чтобы ознакомиться с требованиями:",
        reply_markup=markup
    )

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
@bot.message_handler(func=lambda m: m.text in ["Подать на Хелпера 📝", "Подать на Агента Discord 🛠️"])
def start_application(message):
    global recruitment_open
    if not recruitment_open:
        bot.send_message(message.chat.id, "🔒 **Извините, сейчас набор закрыт.**", parse_mode="Markdown")
        return
    # Определяем роль
    role = "Хелпер" if "Хелпера" in message.text else "Агент поддержки Discord"
    min_age = AGE_HELPER if role == "Хелпер" else AGE_DISCORD
    # Создаем заявку
    user_applications[message.from_user.id] = {
        "username": f"@{message.from_user.username}" if message.from_user.username else "Скрыт",
        "user_id": message.from_user.id,
        "role": role,
        "min_age": min_age
    }
    bot.send_message(
        message.chat.id,
        f"Вы выбрали: **{role}**.\n\nШаг 1: Укажите ваш **реальный возраст** (минимум {min_age} лет):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, process_age)

def process_age(message):
    user_id = message.from_user.id
    if user_id not in user_applications:
        return
    try:
        age_value = int(message.text.strip())
    except:
        bot.send_message(message.chat.id, f"⚠️ Введите число от {user_applications[user_id]['min_age']} до 60.")
        bot.register_next_step_handler(message, process_age)
        return
    min_age = user_applications[user_id]['min_age']
    if age_value < min_age or age_value > 60:
        bot.send_message(message.chat.id, f"⚠️ Возраст должен быть от {min_age} до 60.")
        bot.register_next_step_handler(message, process_age)
        return
    user_applications[user_id]["age"] = str(age_value)
    bot.send_message(
        message.chat.id,
        "Шаг 2: Расскажите о вашем опыте работы (минимум 10 символов):",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, process_experience)

def process_experience(message):
    user_id = message.from_user.id
    if user_id not in user_applications:
        return
    text = message.text.strip()
    if len(text) < 10:
        bot.send_message(message.chat.id, "⚠️ Опишите подробнее, минимум 10 символов.")
        bot.register_next_step_handler(message, process_experience)
        return
    user_applications[user_id]["experience"] = text
    bot.send_message(
        message.chat.id,
        "Шаг 3: Сколько часов в день вы готовы уделять проекту?",
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
        f"• **Готовность:** {data['time']}\n\n"
        "Все верно?"
    )
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row(KeyboardButton("Отправить заявку ✅"))
    markup.row(KeyboardButton("Отменить ❌"))
    bot.send_message(
        message.chat.id,
        summary,
        parse_mode="Markdown",
        reply_markup=markup
    )
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
            f"🕒 **Готовность:** {data['time']}\n"
            f"💼 **Опыт:**\n{data['experience']}"
        )
        inline_kb = InlineKeyboardMarkup()
        inline_kb.row(
            InlineKeyboardButton("Одобрить ✅", callback_data=f"accept_{data['user_id']}"),
            InlineKeyboardButton("Отклонить ❌", callback_data=f"decline_{data['user_id']}")
        )
        bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="Markdown", reply_markup=inline_kb)
        bot.send_message(
            message.chat.id,
            "🎉 Ваша заявка отправлена! Спасибо.",
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
        status_text = "🟢 ОДОБРЕНА"
        notification = "🎉 Ваша заявка одобрена!"
    else:
        status_text = "🔴 ОТКЛОНЕНА"
        notification = "❌ Ваша заявка отклонена!"
    try:
        bot.send_message(user_id, notification, parse_mode="Markdown")
    except:
        pass
    # обновляем сообщение
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=call.message.text + f"\n\n👉 **Решение:** {status_text}",
        reply_markup=None
    )

# --- Обработка команды /admin ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return
    status = "🟢 ОТКРЫТО" if recruitment_open else "🔴 ЗАКРЫТО"
    text = (
        "👑 **Панель управления** 👑\n\n"
        f"Пользователей для рассылки: {len(active_users)}\n"
        f"Прием заявок: **{status}**\n"
        f"Возраст - Хелпер: [{AGE_HELPER}+], Discord: [{AGE_DISCORD}+]\n\n"
        "Выберите действие:"
    )
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        InlineKeyboardButton("🔒 Вкл/Выкл Набор", callback_data="admin_toggle_recruitment")
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

# --- Обработка callback для админ панели ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    global recruitment_open
    # Админ-панель
    if str(call.message.chat.id) == str(ADMIN_CHAT_ID):
        if call.data == "admin_broadcast":
            bot.send_message(ADMIN_CHAT_ID, "Введите текст для рассылки (или 'отмена'):")
            admin_states[ADMIN_CHAT_ID] = "broadcast"
        elif call.data == "admin_toggle_recruitment":
            recruitment_open = not recruitment_open
            status_str = "🟢 ОТКРЫТ" if recruitment_open else "🔴 ЗАКРЫТ"
            bot.answer_callback_query(call.id, f"Статус набора: {status_str}", show_alert=True)
            # Обновляем панель
            admin_panel(call.message)
        return

    # Для решений заявок
    if call.data.startswith('accept_') or call.data.startswith('decline_'):
        handle_decision(call)

# --- Обработка сообщений для рассылки ---
@bot.message_handler(func=lambda msg: str(msg.chat.id) in admin_states and admin_states[msg.chat.id]=='broadcast')
def handle_broadcast(message):
    if message.text.lower() == "отмена":
        bot.send_message(ADMIN_CHAT_ID, "Рассылка отменена.")
        del admin_states[message.chat.id]
        return
    success = 0
    for u in active_users:
        try:
            bot.send_message(u, message.text, parse_mode="Markdown")
            success += 1
        except:
            pass
    bot.send_message(ADMIN_CHAT_ID, f"Рассылка завершена! Разослано: {success} пользователей.")
    del admin_states[message.chat.id]

# Запуск бота
if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
