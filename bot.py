import telebot
from telebot import types
import random
import time
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# НАСТРОЙКИ БОТА
TOKEN = "8957594048:AAFpWXMuYMzqdW89S1m8BKvkePN8TcQKOw0"
ADMIN_CHAT_ID = 8915047087      # Ваш личный Telegram ID
GAME_TOPIC_ID = 12345           # ID игрового топика в вашей группе

bot = telebot.TeleBot(TOKEN)

# --- ИСПРАВЛЕНИЕ: ХРАНЕНИЕ В ПАМЯТИ (БЕЗ ФАЙЛОВ И БД) ---
players = {}
promos = {}

def get_player(user_id):
    uid = str(user_id)
    if uid not in players:
        players[uid] = {
            "balance": 15000,       # Стартовый капитал
            "cars": [],            # Гараж
            "last_work": 0,        # Таймер обычной работы
            "last_high_work": 0    # Таймер высокооплачиваемой работы
        }
    return players[uid]

# --- ИГРОВЫЕ КЛАВИАТУРЫ ---
def game_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_profile = types.InlineKeyboardButton("👤 Мой паспорт", callback_data="game_profile")
    btn_work_menu = types.InlineKeyboardButton("💼 Центр Занятости", callback_data="game_work_menu")
    btn_case = types.InlineKeyboardButton("📦 Открыть контейнер", callback_data="game_case")
    btn_promo = types.InlineKeyboardButton("🎟️ Активировать промокод", callback_data="game_promo_activate")
    
    markup.add(btn_profile, btn_work_menu)
    markup.add(btn_case, btn_promo)
    
    if user_id == ADMIN_CHAT_ID:
        btn_admin = types.InlineKeyboardButton("👑 Панель Создателя [АДМ]", callback_data="game_admin_panel")
        markup.add(btn_admin)
    return markup

def work_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_miner = types.InlineKeyboardButton("⛏️ Шахта (С 14 лет) | От 1,500 до 4,000 руб.", callback_data="game_do_work_miner")
    btn_driver = types.InlineKeyboardButton("🚚 Дальнобой (Нужны права) | От 8,000 до 15,000 руб.", callback_data="game_do_work_driver")
    btn_back = types.InlineKeyboardButton("⬅️ Назад в меню", callback_data="game_main_menu")
    markup.add(btn_miner, btn_driver, btn_back)
    return markup

def admin_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_create = types.InlineKeyboardButton("🎟️ Создать промокод", callback_data="game_admin_promo")
    btn_back = types.InlineKeyboardButton("⬅️ Назад в меню", callback_data="game_main_menu")
    markup.add(btn_create, btn_back)
    return markup

# --- КОМАНДЫ ---
@bot.message_handler(commands=['game', 'start'])
def cmd_game(message):
    if message.chat.type in ['group', 'supergroup']:
        if message.message_thread_id != GAME_TOPIC_ID:
            bot.reply_to(message, "❌ Играть можно только в специально отведенном топике!")
            return

    user_id = message.from_user.id
    get_player(user_id)
    
    remove_markup = types.ReplyKeyboardRemove()
    msg_clean = bot.send_message(message.chat.id, "🔄 Загрузка интерфейса BEST RUSSIA...", reply_markup=remove_markup, message_thread_id=message.message_thread_id)
    try:
        bot.delete_message(message.chat.id, msg_clean.message_id)
    except Exception:
        pass

    text = (
        "🔴 **BEST RUSSIA | Игровой Симулятор**\n\n"
        "Добро пожаловать в текстовую мобильную КРМП вселенную!\n"
        "Устраивайтесь на работу, открывайте контейнеры и собирайте автопарк."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=game_keyboard(user_id), message_thread_id=message.message_thread_id)

# --- ОБРАБОТКА ИГРОВЫХ КНОПОК ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("game_"))
def handle_game(call):
    user_id = call.from_user.id
    p = get_player(user_id)
    
    if call.data == "game_main_menu":
        text = "🔴 **BEST RUSSIA | Игровой Симулятор**\n\nВыберите действие:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_profile":
        cars_str = ", ".join(p['cars']) if p['cars'] else "Отсутствует"
        text = (
            f"📋 **ПАСПОРТ ГРАЖДАНИНА BEST RUSSIA**\n\n"
            f"👤 **Игрок:** {call.from_user.first_name}\n"
            f"💵 **Баланс вирт:** {p['balance']:,} рублей\n"
            f"🚗 **Личный транспорт:** {cars_str}"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_work_menu":
        text = "💼 **Центр Занятости проекта BEST RUSSIA**\n\nВыберите доступную вакансию для заработка:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=work_keyboard())
        bot.answer_callback_query(call.id)

    elif call.data == "game_do_work_miner":
        current_time = time.time()
        if current_time - p['last_work'] < 45:
            left = int(45 - (current_time - p['last_work']))
            bot.answer_callback_query(call.id, f"⏳ Смена на шахте окончена! Отдохните еще {left} сек.", show_alert=True)
            return
        
        salary = random.randint(1500, 4000)
        p['balance'] += salary
        p['last_work'] = current_time
        
        bot.answer_callback_query(call.id, f"⛏️ Вы отработали на Шахте и получили +{salary:,} руб.!", show_alert=True)
        cars_str = ", ".join(p['cars']) if p['cars'] else "Отсутствует"
        text = (
            f"📋 **ПАСПОРТ ГРАЖДАНИНА BEST RUSSIA**\n\n"
            f"👤 **Игрок:** {call.from_user.first_name}\n"
            f"💵 **Баланс вирт:** {p['balance']:,} рублей\n"
            f"🚗 **Личный транспорт:** {cars_str}"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))

    elif call.data == "game_do_work_driver":
        current_time = time.time()
        if current_time - p['last_high_work'] < 300:
            left = int(300 - (current_time - p['last_high_work']))
            bot.answer_callback_query(call.id, f"⏳ Логисты собирают новый груз. Подождите {left // 60} мин. {left % 60} сек.", show_alert=True)
            return
        
        salary = random.randint(8000, 15000)
        p['balance'] += salary
        p['last_high_work'] = current_time
        
        bot.answer_callback_query(call.id, f"🚚 Рейс успешно завершен! Вы заработали +{salary:,} руб.!", show_alert=True)
        cars_str = ", ".join(p['cars']) if p['cars'] else "Отсутствует"
        text = (
            f"📋 **ПАСПОРТ ГРАЖДАНИНА BEST RUSSIA**\n\n"
            f"👤 **Игрок:** {call.from_user.first_name}\n"
            f"💵 **Баланс вирт:** {p['balance']:,} рублей\n"
            f"🚗 **Личный транспорт:** {cars_str}"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))

    elif call.data == "game_case":
        if p['balance'] < 35000:
            bot.answer_callback_query(call.id, "❌ Стоимость открытия элитного контейнера — 35,000 руб.!", show_alert=True)
            return
        
        p['balance'] -= 35000
        loot_type = random.choices(["money", "car"], weights=[75, 25])[0]
        
        if loot_type == "money":
            win_money = random.randint(10000, 85000)
            p['balance'] += win_money
            prize = f"💵 Денежный приз: **{win_money:,} рублей**"
        else:
            win_car = random.choice(["Lada Priora", "Skoda Octavia", "BMW M5 F90", "Rolls-Royce Cullinan"])
            p['cars'].append(win_car)
            prize = f"🚗 Эксклюзивный транспорт: **{win_car}**"
            
        text = f"📦 **Вы успешно открыли контейнер на площадке BEST RUSSIA!**\n🎁 Ваша награда — {prize}!"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_promo_activate":
        msg = bot.send_message(call.message.chat.id, "🎟️ **Введите название промокода для активации:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, user_activate_promo)
        bot.answer_callback_query(call.id)

    elif call.data == "game_admin_panel":
        if user_id != ADMIN_CHAT_ID:
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        text = "👑 **Добро пожаловать в скрытую панель Создателя проекта.**"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())
        bot.answer_callback_query(call.id)

    elif call.data == "game_admin_promo":
        if user_id != ADMIN_CHAT_ID: return
        msg = bot.send_message(call.message.chat.id, "📝 Введите параметры промокода в формате:\n`НАЗВАНИЕ СУММА АКТИВАЦИИ` через пробел.\n\nПример: `BEST2026 50000 10`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_create_promo)
        bot.answer_callback_query(call.id)

# --- ЛОГИКА ПРОМОКОДОВ ---
def admin_create_promo(message):
    if message.from_user.id != ADMIN_CHAT_ID: 
        return
    try:
        parts = message.text.split()
        name = parts[0].upper()
        money = int(parts[1])
        uses = int(parts[2])
        
        promos[name] = {
            "money": money,
            "max_uses": uses,
            "current_uses": 0,
            "activated_users": []
        }
        bot.send_message(message.chat.id, f"✅ Промокод **{name}** успешно создан!\n💰 Награда: {money:,} руб.\n👥 Количество активаций: {uses}", parse_mode="Markdown")
    except Exception:
        bot.send_message(message.chat.id, "❌ Ошибка формата! Используйте шаблон: `НАЗВАНИЕ СУММА АКТИВАЦИИ`")

def user_activate_promo(message):
    user_id = message.from_user.id
