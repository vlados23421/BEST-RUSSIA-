import telebot
from telebot import types
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# НАСТРОЙКИ БОТА (Данные успешно внесены)
TOKEN = "8957594048:AAFpWXMuYMzqdW89S1m8BKvkePN8TcQKOw0"
ADMIN_CHAT_ID = 8915047087  # ID вашего админ-чата / профиля

bot = telebot.TeleBot(TOKEN)

# Временное хранилище данных пользователей в оперативной памяти (без БД)
user_data = {}

# --- КОМАНДА СТАРТ ---
@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    user_data[user_id] = {}  # Очищаем данные сессии кандидатов
    
    # 1. Принудительно удаляем старую нижнюю клавиатуру, оставшуюся от прошлых версий
    remove_markup = types.ReplyKeyboardRemove()
    msg_clean = bot.send_message(message.chat.id, "🔄 Обновление интерфейса...", reply_markup=remove_markup)
    
    try:
        bot.delete_message(message.chat.id, msg_clean.message_id)
    except Exception:
        pass

    # 2. Отправляем новое красивое меню с инлайн-кнопками
    text = (
        "🔴 **BEST RUSSIA | Подача заявок**\n\n"
        "Рады видеть вас! Выберите желаемую должность для подачи анкеты.\n\n"
        "**⚠️ Требования:** Возраст 14+, грамотность, наличие Discord и микрофона."
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_helper = types.InlineKeyboardButton("🛠️ Подать на Хелпера", callback_data="start_helper")
    btn_support = types.InlineKeyboardButton("🎧 Подать на Агента Поддержки", callback_data="start_support")
    markup.add(btn_helper, btn_support)
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

# --- ОБРАБОТКА НАЖАТИЙ КНОПОК ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    # Отмена заполнения
    if call.data == "step_cancel":
        user_data.pop(user_id, None)
        bot.edit_message_text("❌ Заполнение анкеты отменено. Начать заново: /start", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    # Начало анкетирования
    if call.data in ["start_helper", "start_support"]:
        role = "helper" if call.data == "start_helper" else "support"
        user_data[user_id] = {"role": role}
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="step_cancel"))
        
        msg = bot.edit_message_text("1️⃣ **Введите ваше реальное имя и возраст** (например: Иван, 16):", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        bot.register_next_step_handler(msg, process_name_age)
        bot.answer_callback_query(call.id)
        return

    # Решения администрации (Одобрить / Отклонить)
    if call.data.startswith("adm_"):
        _, action, target_user_id, role_type = call.data.split("_")
        target_user_id = int(target_user_id)
        role_name = "Хелпера" if role_type == "helper" else "Агента Поддержки"
        
        old_text = call.message.text
        
        if action == "accept":
            new_text = f"✅ **ЗАЯВКА ОДОБРЕНА** админом @{call.from_user.username}\n\n{old_text}"
            user_text = f"🎉 Поздравляем! Ваша заявка на пост **{role_name}** проекта BEST RUSSIA одобрена! С вами свяжется администратор."
        else:
            new_text = f"❌ **ЗАЯВКА ОТКЛОНЕНА** админом @{call.from_user.username}\n\n{old_text}"
            user_text = f"😔 К сожалению, ваша заявка на пост **{role_name}** проекта BEST RUSSIA была отклонена."
        
        try:
            bot.send_message(target_user_id, user_text)
        except Exception:
            new_text += "\n\n⚠️ *Бот не смог написать пользователю в ЛС*"
            
        bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.answer_callback_query(call.id)

# --- ПОШАГОВЫЙ ОПРОС ---
def process_name_age(message):
    user_id = message.from_user.id
    if user_id not in user_data: 
        return
    
    # Извлекаем числа из сообщения кандидата для проверки возраста
    text_nums = [int(s) for s in message.text.split() if s.isdigit()]
    
    # Если ввели возраст меньше 14 лет — бот сразу завершает опрос
    if text_nums and text_nums[0] < 14:
        bot.send_message(message.chat.id, "⚠️ На проект требуются сотрудники от **14 лет**. Подрастите и приходите позже!")
        user_data.pop(user_id, None)
        return

    user_data[user_id]["name_age"] = message.text
    role = user_data[user_id]["role"]
    
    q = "2️⃣ **Введите ваш игровой ник на BEST RUSSIA** (Ivan_Ivanov):" if role == 'helper' else "2️⃣ **Сколько времени в день вы проводите в Discord?**"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="step_cancel"))
    msg = bot.send_message(message.chat.id, q, parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(msg, process_param_1)

def process_param_1(message):
    user_id = message.from_user.id
    if user_id not in user_data: 
        return
    user_data[user_id]["param_1"] = message.text
    role = user_data[user_id]["role"]
    
    q = "3️⃣ **Каков ваш суточный онлайн?** (например: 4 часа):" if role == 'helper' else "3️⃣ **Оцените ваше знание правил Discord от 0 до 10:**"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="step_cancel"))
    msg = bot.send_message(message.chat.id, q, parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(msg, process_param_2)

def process_param_2(message):
    user_id = message.from_user.id
    if user_id not in user_data: 
        return
    user_data[user_id]["param_2"] = message.text
    role = user_data[user_id]["role"]
    
    q = "4️⃣ **Имеется ли опыт работы?** (Опишите подробно):" if role == 'helper' else "4️⃣ **Опишите ваш опыт модерации в Discord:**"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="step_cancel"))
    msg = bot.send_message(message.chat.id, q, parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(msg, process_param_3)

def process_param_3(message):
    user_id = message.from_user.id
    if user_id not in user_data: 
        return
    user_data[user_id]["param_3"] = message.text
    role = user_data[user_id]["role"]
    
    q = "5️⃣ **Почему именно вы должны занять этот пост?**" if role == 'helper' else "5️⃣ **Расскажите немного о себе и своих качествах:**"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="step_cancel"))
    msg = bot.send_message(message.chat.id, q, parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(msg, process_why_or_about)

def process_why_or_about(message):
    user_id = message.from_user.id
    if user_id not in user_data: 
        return
    user_data[user_id]["why_me_or_about"] = message.text
    
    data = user_data[user_id]
    user_data.pop(user_id, None)  # Полностью очищаем память сессии
    
    bot.send_message(message.chat.id, "🚀 **Ваша заявка успешно отправлена администрации!**", parse_mode="Markdown")
    
    # Формирование сообщения для админ-чата
    role_title = "ХЕЛПЕР" if data['role'] == 'helper' else "АГЕНТ ПОДДЕРЖКИ"
    username = f"@{message.from_user.username}" if message.from_user.username else "Нет юзернейма"
    
    admin_text = (
        f"📥 **НОВАЯ ЗАЯВКА: {role_title}**\n\n"
        f"👤 **Кандидат:** {username} (ID: `{message.from_user.id}`)\n"
        f"📝 **Имя и возраст:** {data['name_age']}\n"
        f"🔹 **Ник / Время в ДС:** {data['param_1']}\n"
        f"🔹 **Онлайн / Знание правил:** {data['param_2']}\n"
        f"💼 **Опыт работы:** {data['param_3']}\n"
        f"❓ **О себе / Почему он:** {data['why_me_or_about']}"
    )
    
    # Кнопки принятия решений для вас под анкетой кандидата
    markup = types.InlineKeyboardMarkup()
    btn_acc = types.InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_accept_{user_id}_{data['role']}")
    btn_rej = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_reject_{user_id}_{data['role']}")
    markup.add(btn_acc, btn_rej)
    
    bot.send_message(ADMIN_CHAT_ID, admin_text, parse_mode="Markdown", reply_markup=markup)

# --- ВЕБ-СЕРВЕР ДЛЯ ВНЕШНЕГО ПИНГА (UPTIME) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

if __name__ == "__main__":
    # Запускаем пинг-сервер в отдельном фоновом потоке, чтобы Render не усыплял бота
    Thread(target=run_web_server, daemon=True).start()
    
    print("Бот проекта BEST RUSSIA успешно запущен и готов к работе!")
    bot.infinity_polling()
