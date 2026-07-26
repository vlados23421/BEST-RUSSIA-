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
ADMIN_CHAT_ID = 8915047087      # Ваш личный ID (для скрытой админки)
GAME_TOPIC_ID = 28           # Укажите ID вашего игрового топика в группе!

bot = telebot.TeleBot(TOKEN)

DATA_FILE = "players_data.json"
PROMO_FILE = "promos_data.json"

# База данных автосалона (Реалистичные цены BEST RUSSIA)
CAR_DEALER = {
    "Lada Priora": 250000,
    "Skoda Octavia": 1200000,
    "BMW M5 F90": 9500000,
    "Rolls-Royce Cullinan": 35000000
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
            "balance": 15000,      # Стартовые вирты
            "exp": 0,              # Текущий опыт
            "level": 1,            # Игровой уровень
            "cars": [],            # Гараж
            "last_work": 0         # Кулдаун работы
        }
        save_data(DATA_FILE, players)
    return players[uid]

# --- ИГРОВОЕ МЕНЮ С ДИНАМИЧЕСКИМИ КНОПКАМИ ---
def game_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_profile = types.InlineKeyboardButton("👤 Мой паспорт", callback_data="game_profile")
    btn_work = types.InlineKeyboardButton("⛏️ Список работ", callback_data="game_work_menu")
    btn_case = types.InlineKeyboardButton("📦 Открыть контейнер [50к]", callback_data="game_case")
    btn_promo = types.InlineKeyboardButton("🎟️ Активировать промокод", callback_data="game_promo_activate")
    btn_shop = types.InlineKeyboardButton("🚗 Автосалон", callback_data="game_shop_menu")
    
    markup.add(btn_profile, btn_work)
    markup.add(btn_case, btn_shop)
    markup.add(btn_promo)
    
    # СКРЫТАЯ АДМИН-КНОПКА (Видна исключительно вам!)
    if user_id == ADMIN_CHAT_ID:
        btn_admin = types.InlineKeyboardButton("👑 Создать промокод [АДМИН]", callback_data="game_admin_promo")
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
    msg_clean = bot.send_message(message.chat.id, "🔄 Загрузка игрового меню...", reply_markup=remove_markup, message_thread_id=message.message_thread_id)
    try: bot.delete_message(message.chat.id, msg_clean.message_id)
    except: pass

    text = (
        "🔴 **BEST RUSSIA | Игровой Симулятор**\n\n"
        "Добро пожаловать в текстовую мобильную КРМП вселенную!\n"
        "Продвигайтесь по карьерной лестнице, открывайте контейнеры и соберите самый элитный автопарк на сервере."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=game_keyboard(user_id), message_thread_id=message.message_thread_id)

# --- ОБРАБОТКА ИГРОВЫХ КНОПОК ---
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
            f"📈 **Игровой уровень:** {p.get('level', 1)} уровень ({p['exp']}/10 EXP)\n"
            f"🚗 **Личный транспорт:** {cars_str}"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_work_menu":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("⛏️ Шахта (Доступно всем | 1.5к - 3.5к)", callback_data="game_do_work_mine"),
            types.InlineKeyboardButton("🚚 Завод (С 3 уровня | 4к - 8к)", callback_data="game_do_work_factory"),
            types.InlineKeyboardButton("Бизнесмен (С 5 уровня | 12к - 25к)", callback_data="game_do_work_biz"),
            types.InlineKeyboardButton("⬅️ В меню", callback_data="game_main_menu")
        )
        bot.edit_message_text("💼 **Выберите доступное место работы:**", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif call.data.startswith("game_do_work_"):
        work_type = call.data.replace("game_do_work_", "")
        current_level = p.get('level', 1)
        current_time = time.time()
        
        # Кулдаун на любую работу: 45 секунд
        if current_time - p['last_work'] < 45:
            left = int(45 - (current_time - p['last_work']))
            bot.answer_callback_query(call.id, f"⏳ Вы устали! Подождите еще {left} сек.", show_alert=True)
            return

        if work_type == "mine":
            salary = random.randint(1500, 3500)
            w_name = "на Шахте"
        elif work_type == "factory":
            if current_level < 3:
                bot.answer_callback_query(call.id, "❌ Нужен минимум 3 уровень!", show_alert=True)
                return
            salary = random.randint(4000, 8000)
            w_name = "на Заводе"
        elif work_type == "biz":
            if current_level < 5:
                bot.answer_callback_query(call.id, "❌ Нужен минимум 5 уровень!", show_alert=True)
                return
            salary = random.randint(12000, 25000)
            w_name = "в своем Офисе"

        p['balance'] += salary
        p['exp'] += 1
        p['last_work'] = current_time
        
        # Система повышения уровней
        if p['exp'] >= 10:
            p['exp'] = 0
            p['level'] = current_level + 1
            bot.send_message(call.message.chat.id, f"🎉 Поздравляем {call.from_user.first_name}! Вы получили **{p['level']} уровень**!")

        save_data(DATA_FILE, players)
        bot.edit_message_text(f"⚒️ Вы успешно отработали смену {w_name} и получили **+{salary:,} рублей** и **+1 EXP**!", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_case":
        if p['balance'] < 50000:
            bot.answer_callback_query(call.id, "❌ Стоимость контейнера: 50,000 руб.", show_alert=True)
            return
        
        p['balance'] -= 50000
        # ИСПРАВЛЕНО: Теперь аргументы весов передаются правильно (70% деньги, 20% опыт, 10% машина)
        loot_type = random.choices(["money", "exp", "car"], weights=[70, 20, 10])[0]
        
        if loot_type == "money":
            win_money = random.randint(15000, 120000)
            p['balance'] += win_money
            prize = f"💵 Деньги: **{win_money:,} рублей**"
        elif loot_type == "exp":
            win_exp = random.randint(2, 5)
            p['exp'] += win_exp
            prize = f"📈 Опыт: **+{win_exp} EXP**"
        else:
            win_car = random.choice(list(CAR_DEALER.keys()))
            p['cars'].append(win_car)
            prize = f"🚗 Автомобиль: **{win_car}**"
            
        save_data(DATA_FILE, players)
        bot.edit_message_text(f"📦 Вы открыли Контейнер на порту!\n🎁 Ваша награда — {prize}!", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_shop_menu":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for car, price in CAR_DEALER.items():
            markup.add(types.InlineKeyboardButton(f"🚗 {car} — {price:,} руб.", callback_data=f"game_buycar_{car}"))
        markup.add(types.InlineKeyboardButton("⬅️ В меню", callback_data="game_main_menu"))
        bot.edit_message_text("🏬 **Автосалон проекта BEST RUSSIA:**", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif call.data.startswith("game_buycar_"):
        car_name = call.data.replace("game_buycar_", "")
        car_price = CAR_DEALER[car_name]
        
        if p['balance'] < car_price:
            bot.answer_callback_query(call.id, f"❌ Не хватает вирт! Цена: {car_price:,} руб.", show_alert=True)
            return
            
        p['balance'] -= car_price
        p['cars'].append(car_name)
        save_data(DATA_FILE, players)
        bot.answer_callback_query(call.id, f"🎉 Вы успешно купили {car_name}!", show_alert=True)
        # Возвращаем в меню
        bot.edit_message_text("🔴 **BEST RUSSIA | Игровой Симулятор**", call.message.chat.id, call.message.message_id, reply_markup=game_keyboard(user_id))

    elif call.data == "game_main_menu":
        bot.edit_message_text("🔴 **BEST RUSSIA | Игровой Симулятор**", call.message.chat.id, call.message.message_id, reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_promo_activate":
