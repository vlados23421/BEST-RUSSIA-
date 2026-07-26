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
ADMIN_CHAT_ID = 8915047087      # Ваш личный ID (для создания промокодов)
GAME_TOPIC_ID = 28           # ID топика в группе, где разрешено играть!

bot = telebot.TeleBot(TOKEN)

DATA_FILE = "players_data.json"
PROMO_FILE = "promos_data.json"

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
            "balance": 5000,       # Стартовые вирты
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
    btn_work = types.InlineKeyboardButton("⛏️ Пойти на Шахту", callback_data="game_work")
    btn_case = types.InlineKeyboardButton("📦 Открыть контейнер", callback_data="game_case")
    btn_promo = types.InlineKeyboardButton("🎟️ Активировать промокод", callback_data="game_promo_activate")
    
    markup.add(btn_profile, btn_work)
    markup.add(btn_case, btn_promo)
    
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
    msg_clean = bot.send_message(message.chat.id, "🔄 Загрузка игрового меню...", reply_markup=remove_markup, message_thread_id=message.message_thread_id)
    try: bot.delete_message(message.chat.id, msg_clean.message_id)
    except: pass

    text = (
        "🔴 **BEST RUSSIA | Игровой Симулятор**\n\n"
        "Добро пожаловать в текстовую мобильную КРМП вселенную!\n"
        "Зарабатывайте вирты на шахте, открывайте элитные контейнеры и соберите самый дорогой автопарк на сервере."
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
            f"📈 **Игровой уровень:** {p['exp']} ур.\n"
            f"🚗 **Личный транспорт:** {cars_str}"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_work":
        current_time = time.time()
        if current_time - p['last_work'] < 60:
            left = int(60 - (current_time - p['last_work']))
            bot.answer_callback_query(call.id, f"⏳ Вы устали! Подождите еще {left} сек.", show_alert=True)
            return
        
        salary = random.randint(1500, 4000)
        p['balance'] += salary
        p['exp'] += random.choice([0, 1])  # Исправлено: шанс 50% получить опыт
        p['last_work'] = current_time
        save_data(DATA_FILE, players)
        
        text = f"⛏️ Вы отлично отработали смену на Шахте проекта BEST RUSSIA и получили **+{salary:,} рублей**!"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_case":
        if p['balance'] < 10000:
            bot.answer_callback_query(call.id, "❌ Недостаточно средств! Стоимость контейнера: 10,000 руб.", show_alert=True)
            return
        
        p['balance'] -= 10000
        # Исправлено: Шансы (60% деньги, 30% опыт, 10% машина)
        loot_type = random.choices(["money", "exp", "car"], weights=[60, 30, 10])[0]
        
        if loot_type == "money":
            win_money = random.randint(3000, 25000)
            p['balance'] += win_money
            prize = f"💵 Деньги: **{win_money:,} рублей**"
        elif loot_type == "exp":
            win_exp = random.randint(1, 3)
            p['exp'] += win_exp
            prize = f"📈 Опыт: **+{win_exp} EXP**"
        else:
            win_car = random.choice(["Lada Priora", "Skoda Octavia", "BMW M5 F90", "Rolls-Royce Cullinan"])
            p['cars'].append(win_car)
            prize = f"🚗 Автомобиль: **{win_car}**"
            
        save_data(DATA_FILE, players)
        
        text = f"📦 Вы успешно открыли контейнер на контейнерной площадке!\n🎁 Ваша награда — {prize}!"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=game_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data == "game_promo_activate":
        msg = bot.send_message(call.message.chat.id, "🎟️ **Введите название промокода для активации:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, user_activate_promo)
        bot.answer_callback_query(call.id)

    elif call.data == "game_admin_promo" and user_id == ADMIN_CHAT_ID:
        msg = bot.send_message(call.message.chat.id, "📝 Введите параметры промокода в формате:\n`НАЗВАНИЕ СУММА АКТИВАЦИИ` (через пробел)\n\nПример: `BEST2026 50000 10`", parse_mode="Markdown")
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
        
        promos[name] = {
            "money": money,
            "max_uses": uses,
            "current_uses": 0,
            "activated_users": []
        }
        save_data(PROMO_FILE, promos)
        bot.send_message(message.chat.id, f"✅ Промокод **{name}** успешно создан!\n💰 Награда: {money:,} руб.\n👥 Активаций: {uses}", parse_mode="Markdown")
    except Exception:
        bot.send_message(message.chat.id, "❌ Ошибка! Неверный формат. Используйте пример: `BEST2026 50000 10`")

def user_activate_promo(message):
    user_id = message.from_user.id
    promo_name = message.text.strip().upper()
    
    if promo_name not in promos:
        bot.send_message(message.chat.id, "❌ Такого промокода не существует!")
        return
        
    p_data = promos[promo_name]
    
    if user_id in p_data["activated_users"]:
        bot.send_message(message.chat.id, "⚠️ Вы уже активировали этот промокод!")
        return
        
    if p_data["current_uses"] >= p_data["max_uses"]:
        bot.send_message(message.chat.id, "😔 Этот промокод больше недействителен (закончились активации).")
        return
        
    p = get_player(user_id)
    p["balance"] += p_data["money"]
    
    p_data["current_uses"] += 1
    p_data["activated_users"].append(user_id)
    
    save_data(DATA_FILE, players)
    save_data(PROMO_FILE, promos)
    
    bot.send_message(message.chat.id, f"🎉 Успешно! Промокод активирован.\n💵 Вы получили **+{p_data['money']:,} рублей** на ваш баланс!", parse_mode="Markdown")

# --- ВЕБ-СЕРВЕР ДЛЯ ВНЕШНЕГО ПИНГА (UPTIME) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Game Bot is alive!")

def run_web_server():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    print("Игровой бот BEST RUSSIA под топики успешно запущен!")
    bot.infinity_polling()
