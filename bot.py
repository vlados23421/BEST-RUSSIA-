import os
import logging
import threading
from flask import Flask
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN", "8957594048:AAEgctfsZve38fv6CwPOXILf3UqI9Gq2WbQ")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "8915047087")

bot = telebot.TeleBot(BOT_TOKEN)

# Настройки в оперативной памяти (сбрасываются при перезапуске сервера Render)
active_users = set()  
recruitment_open = True  
user_applications = {}
admin_states = {}

# Глобальные настройки минимального возраста (можно менять из админки)
age_limits = {
    "helper": 12,
    "discord": 15
}

# --- ВЕБ-СЕРВЕР FLASK ДЛЯ RENDER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Бот BEST RUSSIA онлайн!", 200

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- ЛОГИКА АДМИН-ПАНЕЛИ (КОМАНДА /admin) ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID): return
    status_recruitment = "🟢 ОТКРЫТ" if recruitment_open else "🔴 ЗАКРЫТ"
    
    admin_text = (
        "👑 **ПАНЕЛЬ УПРАВЛЕНИЯ BEST RUSSIA** 👑\n\n"
        f"👥 Пользователей в кэше для рассылки: `{len(active_users)}`\n"
        f"⚙️ Прием анкет сейчас: **{status_recruitment}**\n"
        f"🔞 Ограничения: Хелпер [**{age_limits['helper']}+**] | Discord [**{age_limits['discord']}+**]\n\n"
        "Выберите действие на панели ниже:"
    )
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📢 Рассылка сообщений", callback_data="admin_broadcast"),
        InlineKeyboardButton("🔒 Вкл/Выкл Набор хелперов", callback_data="admin_toggle_recruitment"),
        InlineKeyboardButton("🔞 Изменить Возраст для подачи", callback_data="admin_change_age_menu")
    )
    bot.send_message(message.chat.id, admin_text, parse_mode="Markdown", reply_markup=markup)

# --- ЛОГИКА ПОЛЬЗОВАТЕЛЕЙ ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    active_users.add(message.from_user.id)  
    
    welcome_text = "✨ **Добро пожаловать в систему подачи заявок проекта BEST RUSSIA!** ✨\n\nВыберите интересующую вас вакансию ниже."
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("Подать на Хелпера 📝"), KeyboardButton("Подать на Агента Discord 🛠️"))
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in ["Подать на Хелпера 📝", "Подать на Агента Discord 🛠️"])
def start_application(message):
    if not recruitment_open:
        bot.send_message(message.chat.id, "🔒 **Извините, сейчас прием заявок временно закрыт администрацией.**", parse_mode="Markdown")
        return
    
    chosen_role = "Хелпер" if "Хелпера" in message.text else "Агент поддержки Discord"
    # Берем возраст из наших динамических настроек
    min_age = age_limits["helper"] if chosen_role == "Хелпер" else age_limits["discord"]
    
    user_applications[message.from_user.id] = {
        "username": f"@{message.from_user.username}" if message.from_user.username else "Скрыт", 
        "user_id": message.from_user.id, 
        "role": chosen_role, 
        "min_age": min_age
    }
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
        emoji = "🚀" if data['role'] == "Хелпер" else "🎮"
        admin_message = f"{emoji} **НОВАЯ ЗАЯВКА | {data['role'].upper()}** {emoji}\n\n👤 **Кандидат:** {data['username']} (ID: `{data['user_id']}`)\n🔞 **Возраст:** {data['age']}\n🕒 **Готов уделять:** {data['time']}\n💼 **Опыт работы:**\n{data['experience']}"
        inline_markup = InlineKeyboardMarkup()
        inline_markup.row(InlineKeyboardButton("Одобрить ✅", callback_data=f"accept_{data['user_id']}"), InlineKeyboardButton("Отклонить ❌", callback_data=f"decline_{data['user_id']}"))
        bot.send_message(ADMIN_CHAT_ID, admin_message, parse_mode="Markdown", reply_markup=inline_markup)
        bot.send_message(message.chat.id, "🎉 **Ваша заявка успешно отправлена!** Администрация проекта BEST RUSSIA рассмотрит её в ближайшее время.", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    else:
        bot.send_message(message.chat.id, "❌ Заполнение отменено.", reply_markup=ReplyKeyboardRemove())
    user_applications.pop(user_id, None)

# --- ОБРАБОТКА ИНЛАЙН КНОПОК ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    global recruitment_open
    if str(call.message.chat.id) != str(ADMIN_CHAT_ID): return
    
    if call.data.startswith('accept_') or call.data.startswith('decline_'):
        action, target_user_id = call.data.split('_')
        if action == "accept":
            status_text = "🟢 ОДОБРЕНО АДМИНИСТРАЦИЕЙ"
            user_notification = "🎉 **Поздравляем! Ваша заявка одобрена.** С вами скоро свяжутся."
        else:
            status_text = "🔴 ОТКЛОНЕНО АДМИНИСТРАЦИЕЙ"
            user_notification = "❌ **К сожалению, ваша заявка была отклонена.**"
        try: bot.send_message(target_user_id, user_notification, parse_mode="Markdown")
        except Exception: pass
        bot.edit_message_text(chat_id=ADMIN_CHAT_ID, message_id=call.message.message_id, text=call.message.text + f"\n\n👉 **Решение:** {status_text}", reply_markup=None)
    
    elif call.data == "admin_broadcast":
        bot.send_message(ADMIN_CHAT_ID, "📢 Введите текст для массовой рассылки всем (или напишите 'отмена'):")
        admin_states[ADMIN_CHAT_ID] = "waiting_broadcast"
    
    elif call.data == "admin_toggle_recruitment":
        recruitment_open = not recruitment_open
        status_word = "ОТКРЫТ 🟢" if recruitment_open else "ЗАКРЫТ 🔴"
        bot.answer_callback_query(call.id, f"Статус набора изменен на: {status_word}", show_alert=True)
        admin_panel(call.message)

    elif call.data == "admin_change_age_menu":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("Изменить для Хелперов 🚀", callback_data="set_age_helper"),
            InlineKeyboardButton("Изменить для Discord 🎮", callback_data="set_age_discord")
        )
        bot.send_message(ADMIN_CHAT_ID, "Какую должность настраиваем?", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif call.data in ["set_age_helper", "set_age_discord"]:
        role_key = "helper" if "helper" in call.data else "discord"
        bot.send_message(ADMIN_CHAT_ID, f"🔢 Введите **новый минимальный возраст** для этой должности цифрой (или напишите 'отмена'):")
        admin_states[ADMIN_CHAT_ID] = f"waiting_age_{role_key}"
        bot.answer_callback_query(call.id)

# --- ОБРАБОТКА ТЕКСТА РАССЫЛКИ И ВВОДА ВОЗРАСТА ---
@bot.message_handler(func=lambda msg: str(msg.chat.id) == str(ADMIN_CHAT_ID) and msg.chat.id in admin_states)
def handle_admin_inputs(message):
    state = admin_states[message.chat.id]
    text = message.text.strip()
    
    if text.lower() == 'отмена':
        bot.send_message(ADMIN_CHAT_ID, "❌ Действие отменено.")
        admin_states.pop(message.chat.id, None)
        return
        
    if state == "waiting_broadcast":
        bot.send_message(ADMIN_CHAT_ID, f"🚀 Начинаю рассылку для {len(active_users)} человек...")
        success = 0
