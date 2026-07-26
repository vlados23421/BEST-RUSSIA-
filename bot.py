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
ADMIN_CHAT_ID = 8915047087  # Ваш личный ID (для выдачи виртов и создания промокодов)

# ID ТОПИКА ДЛЯ КАЖДОЙ ИГРОВОЙ ЗОНЫ (Укажите ID топиков вашей группы)
TOPIC_WORK_ID = 26     # Топик: "⛏️ Шахта и Работа"
TOPIC_CASINO_ID = 25   # Топик: "📦 Контейнеры и Казино"
TOPIC_GOV_ID = 24       # Топик: "💼 Правительство и Профили"

bot = telebot.TeleBot(TOKEN)

DATA_FILE = "players_data.json"
PROMO_FILE = "promos_data.json"

# --- СИСТЕМА JSON ---
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
            "balance": 5000,
            "exp": 1,
            "cars": [],
            "last_work": 0
        }
        save_data(DATA_FILE, players)
    return players[uid]

# --- ИГРОВЫЕ КНОПКИ ДЛЯ КАЖДОГО ТОПИКА ---
def get_work_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⛏️ Отработать смену на Шахте", callback_data="game_work"))
    return markup

def get_casino_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📦 Открыть контейнер (10к руб)", callback_data="game_case"))
    return markup

def get_gov_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("👤 Посмотреть мой паспорт", callback_data="game_profile"),
        types.InlineKeyboardButton("🎟️ Активировать промокод", callback_data="game_promo_activate")
    )
    if user_id == ADMIN_CHAT_ID:
        markup.add(types.InlineKeyboardButton("👑 Создать промокод [АДМ]", callback_data="game_admin_promo"))
    return markup

# --- КОМАНДА ЗАПУСКА ИНТЕРФЕЙСА В ТОПИКАХ ---
# Админ пишет эту команду в группе, и бот отправляет нужную кнопку в текущий топик
@bot.message_handler(commands=['spawn_zone'])
def cmd_spawn_zone(message):
    if message.from_user.id != ADMIN_CHAT_ID: 
        return
        
    thread_id = message.message_thread_id
    
    if thread_id == TOPIC_WORK_ID:
        bot.send_message(message.chat.id, "⛏️ **ЛОКАЦИЯ: ШАХТА BEST RUSSIA**\n\nЗдесь вы можете устроиться на временную работу и начать зарабатывать свои первые вирты!", parse_mode="Markdown", reply_markup=get_work_keyboard(), message_thread_id=thread_id)
    elif thread_id == TOPIC_CASINO_ID:
        bot.send_message(message.chat.id, "📦 **ЛОКАЦИЯ: ДОНАТ-КОНТЕЙНЕРЫ**\n\nИспытайте свою удачу! Стоимость открытия — 10,000 рублей. Вы можете выиграть вирты, опыт или элитный автомобиль!", parse_mode="Markdown", reply_markup=get_casino_keyboard(), message_thread_id=thread_id)
    elif thread_id == TOPIC_GOV_ID:
        bot.send_message(message.chat.id, "💼 **ЛОКАЦИЯ: ПРАВИТЕЛЬСТВО**\n\nЗдесь вы можете заказать выписку своего паспорта, проверить автопарк или ввести секретный промокод от разработчиков.", parse_mode="Markdown", reply_markup=get_gov_keyboard(message.from_user.id), message_thread_id=thread_id)
    else:
        bot.send_message(message.chat.id, "⚠️ Этот топик не зарегистрирован в коде бота как игровая зона!", message_thread_id=thread_id)

# --- АДМИН-КОМАНДА: ВЫДАЧА ВИРТОВ (Прямо ответом на сообщение игрока) ---
# Пример использования в топике: /givemoney 50000 (в ответ на сообщение нужного игрока)
@bot.message_handler(commands=['givemoney'])
def cmd_give_money(message):
    if message.from_user.id != ADMIN_CHAT_ID: 
        return
    if not message.reply_to_message:
        bot.send_message(message.chat.id, "⚠️ Ответьте этой командой на сообщение игрока, которому хотите выдать вирты!", message_thread_id=message.message_thread_id)
        return
        
    try:
        parts = message.text.split()
        amount = int(parts[1])
        
        target_user = message.reply_to_message.from_user
        p = get_player(target_user.id)
        p["balance"] += amount
        save_data(DATA_FILE, players)
        
        bot.send_message(message.chat.id, f"👑 Администратор выдал игроку @{target_user.username} **+{amount:,} рублей**!", message_thread_id=message.message_thread_id)
    except Exception:
        bot.send_message(message.chat.id, "⚠️ Ошибка! Используйте формат: `/givemoney СУММА`", parse_mode="Markdown", message_thread_id=message.message_thread_id)

# --- ОБРАБОТКА НАЖАТИЙ (С ПРОВЕРКОЙ ТОПИКА) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("game_"))
def handle_game(call):
    user_id = call.from_user.id
    thread_id = call.message.message_thread_id
    p = get_player(user_id)
    
    # 1. ПРОВЕРКА: Профиль и Промокоды только в Правительстве
    if call.data in ["game_profile", "game_promo_activate", "game_admin_promo"] and thread_id != TOPIC_GOV_ID:
        bot.answer_callback_query(call.id, "❌ Паспортный стол и промокоды доступны только в топике 'Правительство'!", show_alert=True)
        return
        
    # 2. ПРОВЕРКА: Шахта только на Шахте
    if call.data == "game_work" and thread_id != TOPIC_WORK_ID:
        bot.answer_callback_query(call.id, "❌ Работать на шахте можно только в топике 'Шахта / Завод'!", show_alert=True)
        return
        
    # 3. ПРОВЕРКА: Контейнеры только в Казино
    if call.data == "game_case" and thread_id != TOPIC_CASINO_ID:
        bot.answer_callback_query(call.id, "❌ Открывать контейнеры можно только в топике 'Контейнеры / Казино'!", show_alert=True)
        return

    # --- ИГРОВАЯ ЛОГИКА ---
    if call.data == "game_profile":
        cars_str = ", ".join(p['cars']) if p['cars'] else "Отсутствует"
        text = (
            f"📋 **ПАСПОРТ ГРАЖДАНИНА BEST RUSSIA**\n\n"
            f"👤 **Игрок:** {call.from_user.first_name}\n"
            f"💵 **Баланс:** {p['balance']:,} рублей\n"
            f"📈 **Уровень (EXP):** {p['exp']} ур.\n"
            f"🚗 **Личный транспорт:** {cars_str}"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_gov_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_work":
        current_time = time.time()
        if current_time - p['last_work'] < 60:
            left = int(60 - (current_time - p['last_work']))
            bot.answer_callback_query(call.id, f"⏳ Вы устали! Подождите {left} сек.", show_alert=True)
            return
        
        salary = random.randint(1500, 4000)
        p['balance'] += salary
        p['exp'] += random.choice([0, 1, 0, 0])
        p['last_work'] = current_time
        save_data(DATA_FILE, players)
        
        bot.edit_message_text(f"⛏️ Вы отработали смену и получили **+{salary:,} рублей**!\nСледующая смена доступна через минуту.", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_work_keyboard())
        bot.answer_callback_query(call.id)

    elif call.data == "game_case":
        if p['balance'] < 10000:
            bot.answer_callback_query(call.id, "❌ Недостаточно виртов! Стоимость: 10,000 руб.", show_alert=True)
            return
        
        p['balance'] -= 10000
        loot_type = random.choices(["money", "exp", "car"], weights=[50, 35, 15])[0]
        
        if loot_type == "money":
            win_money = random.randint(3000, 25000)
            p['balance'] += win_money
            prize = f"💵 Деньги: **{win_money:,} рублей**"
        elif loot_type == "exp":
            win_exp = random.randint(2, 5)
            p['exp'] += win_exp
            prize = f"📈 Опыт: **+{win_exp} EXP**"
        else:
            win_car = random.choice(["Lada Priora", "Skoda Octavia", "BMW M5 F90", "Rolls-Royce Cullinan"])
            p['cars'].append(win_car)
            prize = f"🚗 Автомобиль: **{win_car}**"
            
        save_data(DATA_FILE, players)
        bot.edit_message_text(f"📦 Вы открыли Донат-Контейнер!\n🎁 Награда — {prize}!", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_casino_keyboard())
        bot.answer_callback_query(call.id)

    elif call.data == "game_promo_activate":
        msg = bot.send_message(call.message.chat.id, "🎟️ Введите промокод:", message_thread_id=thread_id)
        bot.register_next_step_handler(msg, user_activate_promo)
        bot.answer_callback_query(call.id)

    elif call.data == "game_admin_promo":
        msg = bot.send_message(call.message.chat.id, "📝 Формат промокода: `НАЗВАНИЕ СУММА АКТИВАЦИИ`", message_thread_id=thread_id)
        bot.register_next_step_handler(msg, admin_create_promo)
        bot.answer_callback_query(call.id)

# --- ЛОГИКА ПРОМОКОДОВ ---
def admin_create_promo(message):
    if message.from_user.id != ADMIN_CHAT_ID: return
    try:
        parts = message.text.split()
        name = parts[0].upper()
        money = int(parts[1])
        uses = int(parts[2])
        
        promos[name] = {"money": money, "max_uses": uses, "current_uses": 0, "activated_users": []}
        save_data(PROMO_FILE, promos)
        bot.send_message(message.chat.id, f"✅ Промокод **{name}** создан на {uses} активаций по {money:,} руб!", message_thread_id=message.message_thread_id)
    except:
        bot.send_message(message.chat.id, "❌ Ошибка формата!", message_thread_id=message.message_thread_id)

def user_activate_promo(message):
    user_id = message.from_user.id
