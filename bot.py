import telebot
from telebot import types
import random
import time
import json
import os
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN = "8957594048:AAFpWXMuYMzqdW89S1m8BKvkePN8TcQKOw0"
ADMIN_CHAT_ID = 8915047087      
GAME_TOPIC_ID = 28           

bot = telebot.TeleBot(TOKEN)

DATA_FILE = "players_data.json"
PROMO_FILE = "promos_data.json"

# ЦЕНЫ И НАСТРОЙКИ ЭКОНОМИКИ
CASE_PRICE = 25000            # Повысили цену контейнера для ценности
BIZ_PRICE = 150000            # Стоимость покупки бизнеса
BIZ_INCOME = 5000             # Базовый доход бизнеса в час

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
            "balance": 15000,      
            "exp": 1,              
            "cars": [],            
            "biz_level": 0,        # 0 - нет бизнеса, 1+ уровень бизнеса
            "last_work": 0,
            "last_biz_collect": 0  
        }
        save_data(DATA_FILE, players)
    return players[uid]

def main_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_profile = types.InlineKeyboardButton("👤 Паспорт и Имущество", callback_data="game_profile")
    btn_work = types.InlineKeyboardButton("⛏️ Шахта (Заработок)", callback_data="game_work")
    btn_case = types.InlineKeyboardButton("📦 Контейнеры (Рулетка)", callback_data="game_case")
    btn_biz = types.InlineKeyboardButton("🏢 Мой Бизнес", callback_data="game_biz")
    btn_promo = types.InlineKeyboardButton("🎟️ Активация промо", callback_data="game_promo_activate")
    
    markup.add(btn_profile, btn_work)
    markup.add(btn_case, btn_biz)
    markup.add(btn_promo)
    
    if user_id == ADMIN_CHAT_ID:
        btn_admin = types.InlineKeyboardButton("👑 Создать промокод [АДМ]", callback_data="game_admin_promo")
        markup.add(btn_admin)
    return markup

@bot.message_handler(commands=['game', 'start'])
def cmd_game(message):
    if message.chat.type in ['group', 'supergroup'] and message.message_thread_id != GAME_TOPIC_ID:
        bot.reply_to(message, "❌ Играть можно только в специально отведенном топике!")
        return

    user_id = message.from_user.id
    get_player(user_id)
    
    remove_markup = types.ReplyKeyboardRemove()
    msg_clean = bot.send_message(message.chat.id, "🔄 Загрузка экономики BEST RUSSIA...", reply_markup=remove_markup, message_thread_id=message.message_thread_id)
    try: bot.delete_message(message.chat.id, msg_clean.message_id)
    except: pass

    text = (
        "🔴 **BEST RUSSIA | Экономический Симулятор**\n\n"
        "Добро пожаловать на сервер! Здесь решает капитал.\n"
        "• Работайте на шахте с учетом вашего разряда (уровня);\n"
        "• Покупайте бизнесы и качайте пассивную прибыль;\n"
        "• Испытайте удачу в казино `/dice` или на контейнерах."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_keyboard(user_id), message_thread_id=message.message_thread_id)

# --- ИГРА В КАЗИНО (ЧЕРЕЗ КОМАНДУ ДЛЯ АКТИВА В ЧАТЕ) ---
@bot.message_handler(commands=['dice', 'кубик'])
def cmd_dice(message):
    if message.chat.type in ['group', 'supergroup'] and message.message_thread_id != GAME_TOPIC_ID:
        return

    user_id = message.from_user.id
    p = get_player(user_id)
    
    try:
        bet = int(message.text.split()[1])
    except (IndexError, ValueError):
        bot.reply_to(message, "⚠️ Использование: `/dice [сумма]`\nПример: `/dice 5000`", parse_mode="Markdown")
        return
        
    if bet < 1000:
        bot.reply_to(message, "❌ Минимальная ставка в казино — **1,000 рублей**!")
        return
    if p['balance'] < bet:
        bot.reply_to(message, f"❌ У вас нет такой суммы! Ваш баланс: **{p['balance']:,} руб.**")
        return
        
    user_score = random.randint(1, 6) + random.randint(1, 6)
    bot_score = random.randint(1, 6) + random.randint(1, 6)
    
    if user_score > bot_score:
        p['balance'] += bet
        res = f"🎉 Вы выбросили **{user_score}**, а крупье **{bot_score}**.\n✅ Вы выиграли **+{bet:,} рублей**!"
    elif user_score < bot_score:
        p['balance'] -= bet
        res = f"📉 Вы выбросили **{user_score}**, а крупье **{bot_score}**.\n❌ Вы проиграли **-{bet:,} рублей**!"
    else:
        res = f"🤝 Ничья! Оба выбросили по **{user_score}**. Вирты возвращены."
        
    save_data(DATA_FILE, players)
    bot.reply_to(message, res, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("game_"))
def handle_game(call):
    user_id = call.from_user.id
    p = get_player(user_id)
    
    if call.data == "game_profile":
        cars_str = ", ".join(p['cars']) if p['cars'] else "Нет автомобилей"
        biz_status = f"{p['biz_level']} уровня" if p['biz_level'] > 0 else "Отсутствует"
        
        # Налог на имущество (вывод денег из игры)
        tax = (len(p['cars']) * 300) + (p['biz_level'] * 1000)
        if tax > 0 and p['balance'] > tax:
            p['balance'] -= tax
            tax_msg = f"\n⚠️ Списан налог на имущество: **-{tax} руб.**"
        else:
            tax_msg = ""
            
        text = (
            f"📋 **ПАСПОРТ ГРАЖДАНИНА BEST RUSSIA**\n\n"
            f"👤 **Игрок:** {call.from_user.first_name}\n"
            f"💵 **Баланс:** {p['balance']:,} рублей\n"
            f"📈 **Игровой уровень:** {p['exp']} LVL\n"
            f"🏢 **Бизнес:** {biz_status}\n"
            f"🚗 **Гараж:** {cars_str}{tax_msg}"
        )
        save_data(DATA_FILE, players)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_work":
        current_time = time.time()
        if current_time - p['last_work'] < 45:
            left = int(45 - (current_time - p['last_work']))
            bot.answer_callback_query(call.id, f"⏳ Кулдаун! Шахта завалена, подождите {left} сек.", show_alert=True)
            return
            
        # Зарплата зависит от уровня игрока (прогрессия экономики)
        base_salary = random.randint(2000, 5000)
        level_bonus = p['exp'] * 500
        total_salary = base_salary + level_bonus
        
        p['balance'] += total_salary
        if random.random() < 0.4:  
            p['exp'] += 1
            
        p['last_work'] = current_time
        save_data(DATA_FILE, players)
        
        text = f"⛏️ Вы отработали смену хелпером на Шахте.\n💵 С учетом вашего уровня заработано: **+{total_salary:,} рублей**!"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_case":
        if p['balance'] < CASE_PRICE:
            bot.answer_callback_query(call.id, f"❌ Контейнер стоит {CASE_PRICE:,} рублей!", show_alert=True)
            return
            
        p['balance'] -= CASE_PRICE
        loot = random.choices(["loss", "small", "big", "car"], weights=[40, 35, 15, 10])[0]
        
        if loot == "loss":
            prize = "🗑️ Старый глушитель (Продан за **800 руб**)"
            p['balance'] += 800
        elif loot == "small":
            win = random.randint(10000, 20000)
            prize = f"💵 Пачка денег: **{win:,} рублей**"
            p['balance'] += win
        elif loot == "big":
            win = random.randint(40000, 100000)
            prize = f"💰 Слиток золота! Продан за **{win:,} рублей**"
            p['balance'] += win
        else:
            car = random.choice(["Ваз 2107", "Subaru Impreza", "Mercedes AMG GT", "Bugatti Chiron"])
            p['cars'].append(car)
            prize = f"🏎️ Элитный автомобиль: **{car}**"
            
        save_data(DATA_FILE, players)
        text = f"📦 **КОНТЕЙНЕРНАЯ ПЛОЩАДКА**\n\nВы открыли контейнер за {CASE_PRICE:,} руб.\n🎁 Ваш выигрыш: {prize}"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_biz":
        current_time = time.time()
        # Если бизнеса нет
        if p['biz_level'] == 0:
            text = (
                f"🏢 **У вас еще нет коммерческой недвижимости**\n\n"
                f"Вы можете купить свой первый бизнес (Магазин 24/7).\n"
                f"💰 Стоимость покупки: **{BIZ_PRICE:,} рублей**.\n"
                f"📈 Он будет приносить пассивный доход **{BIZ_INCOME:,} руб./час**."
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🛒 Купить Бизнес", callback_data="game_biz_buy"))
            markup.add(types.InlineKeyboardButton("⬅️ Меню", callback_data="game_profile"))
        else:
            # Считаем пассивную прибыль (максимум за 12 часов, чтобы не было дисбаланса)
            hours = int((current_time - p['last_biz_collect']) / 3600)
            if hours > 12: hours = 12
            
            income = hours * (BIZ_INCOME * p['biz_level'])
            upgrade_cost = p['biz_level'] * 100000
            
            text = (
                f"🏢 **УПРАВЛЕНИЕ БИЗНЕСОМ**\n\n"
                f"📊 Уровень предприятия: **{p['biz_level']} LVL**\n"
