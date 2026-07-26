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
ADMIN_CHAT_ID = 8915047087      # Ваш личный ID 
GAME_TOPIC_ID = 28           # ID топика в группе, где разрешено играть

bot = telebot.TeleBot(TOKEN)

DATA_FILE = "players_data.json"
PROMO_FILE = "promos_data.json"

# База данных автомобилей (Класс, Государственная цена покупки)
CARS_DATABASE = {
    "Lada Priora": {"class": "Низкий", "price": 300000},
    "Vaz 2107": {"class": "Низкий", "price": 100000},
    "Skoda Octavia": {"class": "Средний", "price": 1200000},
    "BMW M5 F90": {"class": "Высокий", "price": 9500000},
    "Rolls-Royce Cullinan": {"class": "Высокий", "price": 45000000}
}

# --- СИСТЕМА ДАННЫХ (JSON) ---
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
            "balance": 15000,      # Стартовые вирты повышено
            "exp": 1,              # Уровень
            "cars": [],            # Гараж
            "last_work": 0         # Кулдаун работы
        }
        save_data(DATA_FILE, players)
    return players[uid]

# --- ИГРОВОЕ МЕНЮ ---
def game_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_profile = types.InlineKeyboardButton("👤 Мой паспорт", callback_data="game_profile")
    btn_work = types.InlineKeyboardButton("⛏️ Центр Занятости", callback_data="game_work_menu")
    btn_case = types.InlineKeyboardButton("📦 Контейнеры", callback_data="game_case_menu")
    btn_promo = types.InlineKeyboardButton("🎟️ Активировать промо", callback_data="game_promo_activate")
    btn_sell = types.InlineKeyboardButton("🚗 Продать машину гос-ву", callback_data="game_sell_car_menu")
    
    markup.add(btn_profile, btn_work)
    markup.add(btn_case, btn_promo)
    markup.add(btn_sell)
    
    # Кнопка отображается СТРОГО администратору
    if user_id == ADMIN_CHAT_ID:
        btn_admin = types.InlineKeyboardButton("👑 Создать промокод [АДМ]", callback_data="game_admin_promo")
        markup.add(btn_admin)
    return markup

# --- КОМАНДА СТАРТ / ИГРА ---
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
        "🔴 **BEST RUSSIA | Мобильный Симулятор**\n\n"
        "Добро пожаловать в текстовую вселенную КРМП!\n"
        "Продвигайтесь по карьерной лестнице, открывайте прибыльные контейнеры, играйте в казино и соберите автопарк мечты."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=game_keyboard(user_id), message_thread_id=message.message_thread_id)

# --- ИГРА В КОСТИ (КАЗИНО) ---
@bot.message_handler(commands=['dice'])
def cmd_dice(message):
    if message.chat.type in ['group', 'supergroup'] and message.message_thread_id != GAME_TOPIC_ID:
        return

    user_id = message.from_user.id
    p = get_player(user_id)
    
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        bot.reply_to(message, "⚠️ Использование: `/dice [сумма вирт]`", parse_mode="Markdown")
        return
        
    bet = int(parts[1])
    if bet < 1000:
        bot.reply_to(message, "❌ Минимальная ставка в казино — **1,000 рублей**!", parse_mode="Markdown")
        return
    if p['balance'] < bet:
        bot.reply_to(message, "❌ У вас нет такой суммы на руках!")
        return
        
    user_score = random.randint(1, 6) + random.randint(1, 6)
    bot_score = random.randint(1, 6) + random.randint(1, 6)
    
    if user_score > bot_score:
        p['balance'] += bet
        res = f"🎉 Вы выигрываете **+{bet:,} рублей**! ({user_score} против {bot_score})"
    elif user_score < bot_score:
        p['balance'] -= bet
        res = f"📉 Вы проиграли **-{bet:,} рублей**! ({user_score} против {bot_score})"
    else:
        res = f"🤝 Ничья! Вирты остаются при вас. ({user_score} против {bot_score})"
        
    save_data(DATA_FILE, players)
    bot.reply_to(message, res, parse_mode="Markdown")

# --- ОБРАБОТКА CALLBACK НАЖАТИЙ ---
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
            f"📈 **Игровой уровень:** {p['exp']} EXP\n"
            f"🚗 **Личный транспорт:** {cars_str}"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_work_menu":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("⛏️ Шахта (С 1 уровня)", callback_data="game_do_work_shaft"),
            types.InlineKeyboardButton("🌲 Лесопилка (Со 3 уровня)", callback_data="game_do_work_forest"),
            types.InlineKeyboardButton("💰 Инкассация (С 5 уровня)", callback_data="game_do_work_cash"),
            types.InlineKeyboardButton("⬅️ В меню", callback_data="game_back_main")
        )
        bot.edit_message_text("💼 **Выберите место работы в Центре Занятости:**", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif call.data.startswith("game_do_work_"):
        current_time = time.time()
        if current_time - p['last_work'] < 45:
            left = int(45 - (current_time - p['last_work']))
            bot.answer_callback_query(call.id, f"⏳ Кулдаун! Отдохните еще {left} сек.", show_alert=True)
            return
            
        work_type = call.data.split("_")[-1]
        
        if work_type == "shaft":
            salary = random.randint(2000, 4500)
            job_name = "на Шахте"
        elif work_type == "forest":
            if p['exp'] < 3:
                bot.answer_callback_query(call.id, "❌ Нужен 3 уровень!", show_alert=True)
                return
            salary = random.randint(5000, 9000)
            job_name = "на Лесопилке"
        else:
            if p['exp'] < 5:
                bot.answer_callback_query(call.id, "❌ Нужен 5 уровень!", show_alert=True)
                return
            salary = random.randint(12000, 22000)
            job_name = "в Службе Инкассации"
            
        p['balance'] += salary
        p['exp'] += random.choice()
        p['last_work'] = current_time
        save_data(DATA_FILE, players)
        
        bot.edit_message_text(f"✅ Вы успешно отработали смену {job_name} и получили **+{salary:,} рублей**! (+1 EXP)", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_case_menu":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📦 Обычный контейнер (50,000 руб.)", callback_data="game_open_case_low"),
            types.InlineKeyboardButton("💎 Элитный контейнер (500,000 руб.)", callback_data="game_open_case_high"),
            types.InlineKeyboardButton("⬅️ В меню", callback_data="game_back_main")
        )
        bot.edit_message_text("📦 **Выберите класс контейнера для открытия:**", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif call.data.startswith("game_open_case_"):
        case_type = call.data.split("_")[-1]
        cost = 50000 if case_type == "low" else 500000
        
        if p['balance'] < cost:
            bot.answer_callback_query(call.id, f"❌ Недостаточно вирт! Стоимость: {cost:,} руб.", show_alert=True)
            return
            
        p['balance'] -= cost
        
        if case_type == "low":
            loot = random.choices(["money", "car"], weights=)[0]
            if loot == "money":
                prize_money = random.randint(15000, 75000)
                p['balance'] += prize_money
                res_text = f"💵 Деньги: **{prize_money:,} рублей**"
            else:
                car = random.choice(["Lada Priora", "Vaz 2107"])
                p['cars'].append(car)
                res_text = f"🚗 Автомобиль: **{car}** ({CARS_DATABASE[car]['class']} класс)"
        else:
            loot = random.choices(["money", "car"], weights=)[0]
            if loot == "money":
                prize_money = random.randint(150000, 800000)
