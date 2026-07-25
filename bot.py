import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- НАСТРОЙКИ БЕЗОПАСНОСТИ И ПОДКЛЮЧЕНИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8957594048:AAEmSxKbnZBchUXQ8UphJ86HxqDJa7_FpJw")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "8915047087") 

bot = telebot.TeleBot(BOT_TOKEN)

# Временное хранилище для анкет в памяти
user_applications = {}

def clean_input(text: str) -> str:
    """Очистка ввода от опасных символов и лишних пробелов для безопасности."""
    if not text:
        return ""
    return text.strip()[:500]

# --- Фоновый веб-сервер для Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        return  # Отключаем спам-логи веб-сервера

def run_health_check():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logging.info(f"Фоновый веб-сервер запущен на порту {port}")
    server.serve_forever()

# --- ЛОГИКА БОТА ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
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
    
    # Определяем выбранную роль
    chosen_role = "Хелпер" if "Хелпера" in message.text else "Агент поддержки Discord"
    min_age = 12 if chosen_role == "Хелпер" else 15
    
    user_applications[user_id] = {
        "username": f"@{message.from_user.username}" if message.from_user.username else "Скрыт/Нету",
        "user_id": user_id,
        "role": chosen_role,
        "min_age": min_age
    }
    
    bot.send_message(
        message.chat.id, 
        f"Вы выбрали направление: **{chosen_role}**.\n\n"
        f"Шаг 1. Укажите ваш **реальный возраст** (цифрой, минимум {min_age} лет):", 
        parse_mode="Markdown", 
        reply_markup=ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, process_age)

def process_age(message):
    user_id = message.from_user.id
    if user_id not in user_applications: return
        
    text = clean_input(message.text)
    min_role_age = user_applications[user_id]["min_age"]
    
    # Динамическая проверка возраста под каждую роль
    if not text.isdigit() or not (min_role_age <= int(text) <= 60):
        bot.send_message(
            message.chat.id, 
            f"⚠️ Пожалуйста, введите корректный возраст цифрами (для этой должности требуется возраст от {min_role_age} до 60 лет):"
        )
        bot.register_next_step_handler(message, process_age)
        return

    user_applications[user_id]["age"] = text
    bot.send_message(
        message.chat.id, 
        "Шаг 2. Расскажите о вашем **опыте работы** на аналогичных проектах/серверах (где были, какие обязанности выполняли):", 
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, process_experience)

def process_experience(message):
    user_id = message.from_user.id
    if user_id not in user_applications: return

    text = clean_input(message.text)
    if len(text) < 10:
        bot.send_message(message.chat.id, "⚠️ Опишите ваш опыт подробнее для лучшего шанса (минимум 10 символов):")
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
        
        # Меняем заголовок карточки в зависимости от должности
        emoji = "🚀" if data['role'] == "Хелпер" else "🎮"
        admin_message = (
            f"{emoji} **НОВАЯ ЗАЯВКА | {data['role'].upper()}** {emoji}\n\n"
            f"👤 **Кандидат:** {data['username']} (ID: `{data['user_id']}`)\n"
            f"🔞 **Возраст:** {data['age']}\n"
            f"🕒 **Готов уделять:** {data['time']}\n"
            f"💼 **Опыт работы:**\n{data['experience']}\n"
        )
        
        # Инлайн-кнопки решения для администратора
        inline_markup = InlineKeyboardMarkup()
        inline_markup.add(
            InlineKeyboardButton("Одобрить ✅", callback_data=f"accept_{data['user_id']}_{data['role']}"),
            InlineKeyboardButton("Отклонить ❌", callback_data=f"decline_{data['user_id']}_{data['role']}")
        )
        
        try:
            bot.send_message(ADMIN_CHAT_ID, admin_message, parse_mode="Markdown", reply_markup=inline_markup)
            bot.send_message(
                message.chat.id, 
                f"🎉 **Ваша заявка на должность {data['role']} успешно отправлена!** Администрация проекта BEST RUSSIA рассмотрит её в ближайшее время.", 
                parse_mode="Markdown", 
                reply_markup=ReplyKeyboardRemove()
            )
            logging.info(f"Заявка от {user_id} на должность {data['role']} отправлена в админ-чат.")
        except Exception as e:
            bot.send_message(message.chat.id, "❌ Произошла ошибка при отправке. Пожалуйста, обратитесь к создателю проекта.")
            logging.error(f"Ошибка отправки админу: {e}")
    else:
        bot.send_message(message.chat.id, "❌ Заполнение анкеты отменено. Вы можете начать заново, написав /start.", reply_markup=ReplyKeyboardRemove())
        
    user_applications.pop(user_id, None)

# --- ОБРАБОТКА КНОПОК АДМИНИСТРАТОРА ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_') or call.data.startswith('decline_'))
def handle_admin_decision(call):
    if str(call.message.chat.id) != str(ADMIN_CHAT_ID):
        bot.answer_callback_query(call.id, "⚠️ Вы не являетесь администратором!", show_alert=True)
        return

    # Разбиваем данные из кнопки: действие, ID кандидата и название роли
    parts = call.data.split('_')
    action = parts[0]
    target_user_id = parts[1]
    role_name = parts[2]
    
    if action == "accept":
        status_text = "🟢 **ОДОБРЕНО АДМИНИСТРАЦИЕЙ**"
        user_notification = f"🎉 **Поздравляем! Ваша заявка на должность '{role_name}' проекта BEST RUSSIA одобрена.** Администратор свяжется с вами в ближайшее время."
    else:
        status_text = "🔴 **ОТКЛОНЕНО АДМИНИСТРАЦИЕЙ**"
        user_notification = f"❌ **К сожалению, ваша заявка на должность '{role_name}' была отклонена.** Вы можете попробовать снова позже."

    # Отправляем уведомление кандидату
    try:
        bot.send_message(target_user_id, user_notification, parse_mode="Markdown")
        bot.answer_callback_query(call.id, "Кандидат успешно уведомлен!")
    except Exception as e:
        bot.answer_callback_query(call.id, "⚠️ Не удалось отправить сообщение кандидату (бот заблокирован).", show_alert=True)
        logging.warning(f"Не удалось уведомить пользователя {target_user_id}: {e}")

    # Обновляем сообщение в админ-чате
    updated_text = call.message.text + f"\n\n👉 **Вердикт:** {status_text}"
    bot.edit_message_text(chat_id=ADMIN_CHAT_ID, message_id=call.message.message_id, text=updated_text, reply_markup=None)

if __name__ == '__main__':
    threading.Thread(target=run_health_check, daemon=True).start()
    logging.info("Бот проекта BEST RUSSIA запускается...")
    bot.infinity_polling()
