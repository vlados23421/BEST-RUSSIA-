import telebot
from telebot import types
import random
import time
import json
import os
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# НАСТРОЙКИ БОТА
TOKEN = "8957594048:AAFpWXMuYMzqdW89S1m8BKvkePN8TcQKOw0"
ADMIN_CHAT_ID = 8915047087      # Ваш личный ID (для скрытой кнопки)
GAME_TOPIC_ID = 28           # ID топика в группе, где разрешено играть!

bot = telebot.TeleBot(TOKEN)

DATA_FILE = "players_data.json"
PROMO_FILE = "promos_data.json"

# СИСТЕМА ДАННЫХ (JSON)
def load_data(file_name, default_factory):
    if os.path.exists(file_name):
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_factory()
    return default_factory()

def save_data(file_name, data):
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

players = load_data(DATA_FILE, dict)
promos = load_data(PROMO_FILE, dict)

def get_player(user_id):
    uid = str(user_id)
    if uid not in players:
        players[uid] = {
            "balance": 5000,       # Стартовые вирты
            "exp": 1,              # Уровень
            "cars": [],            # Гараж
            "last_work": 0         # Кулдаун работы
        }
        save_data(DATA_FILE, players)
    return players[uid]

# ИГРОВОЕ МЕНЮ (С динамической админ-кнопкой)
def game_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_profile = types.InlineKeyboardButton("👤 Мой паспорт", callback_data="game_profile")
    btn_work = types.InlineKeyboardButton("⛏️ Шахта / Завод", callback_data="game_work")
    btn_case = types.InlineKeyboardButton("📦 Контейнеры", callback_data="game_case")
    btn_promo = types.InlineKeyboardButton("🎟️ Промокод", callback_data="game_promo_activate")
    btn_casino = types.InlineKeyboardButton("🎰 Казино (Кости)", callback_data="game_casino_menu")
    btn_market = types.InlineKeyboardButton("🚗 Б/У Рынок", callback_data="game_market_menu")
    
    markup.add(btn_profile, btn_work)
    markup.add(btn_case, btn_promo)
    markup.add(btn_casino, btn_market)
    
    # Кнопка отображается ТОЛЬКО вам
    if user_id == ADMIN_CHAT_ID:
        btn_admin = types.InlineKeyboardButton("👑 Создать промокод [АДМ]", callback_data="game_admin_promo")
        markup.add(btn_admin)
    return markup

# КОМАНДА СТАРТ / ИГРА
@bot.message_handler(commands=['game', 'start'])
def cmd_game(message):
    if message.chat.type in ['group', 'supergroup']:
        if message.message_thread_id != GAME_TOPIC_ID:
            bot.reply_to(message, "❌ Играть можно только в специально отведенном топике!")
            return

    user_id = message.from_user.id
    get_player(user_id)
    
    remove_markup = types.ReplyKeyboardRemove()
    msg_clean = bot.send_message(message.chat.id, "🔄 Загрузка игрового меню...", reply_markup=remove_markup, message_thread_id=message.message_thread_id)
    try:
        bot.delete_message(message.chat.id, msg_clean.message_id)
    except Exception:
        pass

    text = (
        "🔴 **BEST RUSSIA | Игровой Симулятор**\n\n"
        "Добро пожаловать в текстовую мобильную КРМП вселенную!\n"
        "Зарабатывайте вирты, открывайте контейнеры, играйте в казино и соберите лучший автопарк."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=game_keyboard(user_id), message_thread_id=message.message_thread_id)

# ОБРАБОТКА ИГРОВЫХ КНОПОК
@bot.callback_query_handler(func=lambda call: call.data.startswith("game_"))
def handle_game(call):
    user_id = call.from_user.id
    p = get_player(user_id)
    
    if call.data == "game_profile":
        cars_str = ", ".join(p['cars']) if p['cars'] else "Отсутствует"
        text = (
            f"📋 **ПАСПОРТ ГРАЖДАНИНА BEST RUSSIA**\n\n"
            f"👤 **Игрок:** {call.from_user.first_name}\n"
            f"💵 **Баланс вирт:** {p['balance']:,} рублей\n"
            f"📈 **Игровой уровень:** {p['exp']} ур.\n"
            f"🚗 **Личный транспорт:** {cars_str}"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_work":
        current_time = time.time()
        if current_time - p['last_work'] < 60:
            left = int(60 - (current_time - p['last_work']))
            bot.answer_callback_query(call.id, f"⏳ Вы сильно устали! Подождите еще {left} сек.", show_alert=True)
            return
        
        salary = random.randint(1500, 4500)
        p['balance'] += salary
        p['exp'] += random.choice([0, 1])
        p['last_work'] = current_time
        save_data(DATA_FILE, players)
        
        text = f"⛏️ Вы отлично отработали смену и получили **+{salary:,} рублей**!"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_case":
        if p['balance'] < 15000:
            bot.answer_callback_query(call.id, "❌ Недостаточно средств! Стоимость контейнера: 15,000 руб.", show_alert=True)
            return
        
        p['balance'] -= 15000
        loot_type = random.choices(["money", "car"], weights=[70, 30])[0]
        
        if loot_type == "money":
            win_money = random.randint(5000, 35000)
            p['balance'] += win_money
            prize = f"💵 Деньги: **{win_money:,} рублей**"
        else:
            win_car = random.choice(["Lada Priora", "Skoda Octavia", "BMW M5 F90", "Rolls-Royce Cullinan"])
            p['cars'].append(win_car)
            prize = f"🚗 Автомобиль: **{win_car}**"
            
        save_data(DATA_FILE, players)
        
        text = f"📦 Вы открыли Контейнер!\n🎁 Ваша награда — {prize}!"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_promo_activate":
        msg = bot.send_message(call.message.chat.id, "🎟️ **Введите название промокода для активации:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, user_activate_promo)
        bot.answer_callback_query(call.id)

    elif call.data == "game_casino_menu":
        text = "🎰 **Добро пожаловать в Казино Калигула!**\n\nИспользуйте команду для игры:\n`/dice [сумма]`\n\nПример: `/dice 5000`"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_market_menu":
        text = "🚗 **Б/У Авторынок проекта**\n\nВы можете продать государству свою последнюю машину за **7,000 рублей**.\nИспользуйте команду: `/sellcar`"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_admin_promo" and user_id == ADMIN_CHAT_ID:
        msg = bot.send_message(call.message.chat.id, "📝 Введите параметры промокода в формате:\n`НАЗВАНИЕ СУММА АКТИВАЦИИ` (через пробел)\n\nПример: `BEST2026 50000 10`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_create_promo)
        bot.answer_callback_query(call.id)

# КОМАНДЫ КАЗИНО И РЫНКА
@bot.message_handler(commands=['dice'])
def cmd_dice(message):
    if message.chat.type in ['group', 'supergroup'] and message.message_thread_id != GAME_TOPIC_ID:
        return
        
    user_id = message.from_user.id
    p = get_player(user_id)
    
    try:
        bet = int(message.text.split()[1])
    except Exception:
        bot.reply_to(message, "⚠️ Формат: `/dice [сумма]`", parse_mode="Markdown")
        return
        
    if bet <= 0:
        bot.reply_to(message, "❌ Ставка должна быть больше 0!")
        return
    if p['balance'] < bet:
        bot.reply_to(message, "❌ У вас нет такой суммы!")
        return
        
    user_score = random.randint(1, 6)
    bot_score = random.randint(1, 6)
    
    if user_score > bot_score:
        p['balance'] += bet
        res = f"🎉 Вы выкинули {user_score}, а бот {bot_score}. **Вы выиграли {bet:,} руб!**"
    elif user_score < bot_score:
        p['balance'] -= bet
        res = f"📉 Вы выкинули {user_score}, а бот {bot_score}. **Вы проиграли {bet:,} руб.**"
    else:
        res = f"🤝 Ничья! Оба выкинули {user_score}. Вирты сохранены."
        
    save_data(DATA_FILE, players)
    bot.reply_to(message, res)

@bot.message_handler(commands=['sellcar'])
def cmd_sellcar(message):
    if message.chat.type in ['group', 'supergroup'] and message.message_thread_id != GAME_TOPIC_ID:
        return
        
    user_id = message.from_user.id
    p = get_player(user_id)
    
    if not p['cars']:
        bot.reply_to(message, "❌ У вас нет машин для продажи!")
        return
        
    sold = p['cars'].pop()  # Продаем последнюю машину
    p['balance'] += 7000
    save_data(DATA_FILE, players)
    bot.reply_to(message, f"🚗 Вы успешно продали государству **{sold}** за **7,000 руб**!")

# ЛОГИКА ПРОМОКОДОВ
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
        save_data(PROMO_FILE, promos)
        bot.send_message(message.chat.id, f"✅ Промокод **{name}** успешно создан!\n💰 Награда: {money:,} руб.\n👥 Активаций: {uses}", parse_mode="Markdown")
