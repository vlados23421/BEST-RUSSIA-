import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# --- НАСТРОЙКИ БЕЗОПАСНОСТИ И ПОДКЛЮЧЕНИЯ ---
# Ваши данные успешно интегрированы в переменные по умолчанию
BOT_TOKEN = os.getenv("BOT_TOKEN", "8957594048:AAEgctfsZve38fv6CwPOXILf3UqI9Gq2WbQ")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "8915047087") 

bot = telebot.TeleBot(BOT_TOKEN)

# Временное хранилище для анкет в памяти
user_applications = {}

def clean_input(text: str) -> str:
    """Очистка ввода от опасных символов и лишних пробелов для безопасности."""
    if not text:
        return ""
    return text.strip()[:500]

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "✨ **Добро пожаловать в систему подачи заявок проекта BEST RUSSIA!** ✨\n\n"
        "Здесь вы можете оставить свою анкетирование на должность **Хелпера**.\n"
        "Для начала заполнения нажмите на кнопку ниже."
    )
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("Подать заявку 📝"))
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "Подать заявку 📝")
def start_application(message):
    user_id = message.from_user.id
    user_applications[user_id] = {
        "username": f"@{message.from_user.username}" if message.from_user.username else "Скрыт/Нету",
        "user_id": user_id
    }
    bot.send_message(
        message.chat.id, 
        "Шаг 1. Укажите ваш **реальный возраст** (цифрой):", 
        parse_mode="Markdown", 
        reply_markup=ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, process_age)

def process_age(message):
    user_id = message.from_user.id
    if user_id not in user_applications:
        return
        
    text = clean_input(message.text)
    
    # Валидация возраста для безопасности данных
    if not text.isdigit() or not (12 <= int(text) <= 60):
        bot.send_message(message.chat.id, "⚠️ Пожалуйста, введите корректный возраст цифрами (от 12 до 60 лет):")
        bot.register_next_step_handler(message, process_age)
        return

    user_applications[user_id]["age"] = text
    bot.send_message(message.chat.id, "Шаг 2. Расскажите о вашем **опыте работы** на аналогичных проектах (где были, какие должности занимали):", parse_mode="Markdown")
    bot.register_next_step_handler(message, process_experience)

def process_experience(message):
    user_id = message.from_user.id
    if user_id not in user_applications:
        return

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
    if user_id not in user_applications:
        return

    text = clean_input(message.text)
    user_applications[user_id]["time"] = text

    # Финальное подтверждение
    data = user_applications[user_id]
    summary = (
        "📋 **Проверьте ваши данные перед отправкой:**\n\n"
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
    if user_id not in user_applications:
        return

    if message.text == "Отправить заявку ✅":
        data = user_applications[user_id]
        
        # Формируем красивую карточку для администрации
        admin_message = (
            "🚀 **НОВАЯ ЗАЯВКА НА ХЕЛПЕРА | BEST RUSSIA** 🚀\n\n"
            f"👤 **Кандидат:** {data['username']} (ID: `{data['user_id']}`)\n"
            f"🔞 **Возраст:** {data['age']}\n"
            f"🕒 **Готов уделять:** {data['time']}\n"
            f"💼 **Опыт работы:**\n{data['experience']}\n"
        )
        
        try:
            bot.send_message(ADMIN_CHAT_ID, admin_message, parse_mode="Markdown")
            bot.send_message(
                message.chat.id, 
                "🎉 **Ваша заявка успешно отправлена!** Администрация проекта BEST RUSSIA рассмотрит её в ближайшее время.", 
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove()
            )
        except Exception as e:
            bot.send_message(message.chat.id, "❌ Произошла ошибка при отправке. Пожалуйста, обратитесь к создателю проекта.")
            print(f"Ошибка отправки админу: {e}")
            
    else:
        bot.send_message(
            message.chat.id, 
            "❌ Заполнение анкеты отменено. Вы можете начать заново, написав /start.", 
            reply_markup=ReplyKeyboardRemove()
        )
        
    user_applications.pop(user_id, None)

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

if __name__ == '__main__':
    # Запуск фонового веб-сервера для Render
    threading.Thread(target=run_health_check, daemon=True).start()

    print("Бот проекта BEST RUSSIA запущен...")
    bot.infinity_polling()
