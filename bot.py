import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

# НАСТРОЙКИ БОТА
TOKEN = "8957594048:AAFpWXMuYMzqdW89S1m8BKvkePN8TcQKOw0"
ADMIN_CHAT_ID = 8915047087  # ID группы, куда приходят анкеты

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Фабрика для обработки решений админов
class AdminDecision(CallbackData, prefix="adm"):
    action: str  # accept / reject
    user_id: int
    role: str    # helper / support

# Состояния опроса
class Form(StatesGroup):
    role = State()            # Выбранная роль
    name_age = State()        # Имя и возраст
    param_1 = State()         # Хелпер: Ник | Поддержка: Время в ДС
    param_2 = State()         # Хелпер: Онлайн | Поддержка: Знание правил
    param_3 = State()         # Хелпер: Опыт | Поддержка: Опыт модерации
    why_me_or_about = State() # Финальный развернутый ответ

# Кнопки главного меню
def main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛠️ Подать на Хелпера", callback_data="start_helper")
    builder.button(text="🎧 Подать на Агента Поддержки", callback_data="start_support")
    return builder.adjust(1).as_markup()

# Кнопки управления в процессе анкетирования
def control_kb(show_back=True):
    builder = InlineKeyboardBuilder()
    if show_back:
        builder.button(text="⬅️ Назад", callback_data="step_back")
    builder.button(text="❌ Отмена", callback_data="step_cancel")
    return builder.adjust(2 if show_back else 1).as_markup()

# Кнопки для администрации
def admin_decision_kb(user_id: int, role: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить", callback_data=AdminDecision(action="accept", user_id=user_id, role=role))
    builder.button(text="❌ Отклонить", callback_data=AdminDecision(action="reject", user_id=user_id, role=role))
    return builder.adjust(2).as_markup()

# --- СТАРТ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    text = (
        "🔴 **BEST RUSSIA | Подача заявок**\n\n"
        "Рады видеть вас! Выберите желаемую должность для подачи анкеты.\n\n"
        "**⚠️ Требования:** Возраст 14+, грамотность, наличие Discord и микрофона."
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=main_kb())

# --- УПРАВЛЕНИЕ ШАГАМИ (НАЗАД / ОТМЕНА) ---
@dp.callback_query(F.data == "step_cancel")
async def cancel_wizard(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Заполнение анкеты отменено. Вы можете начать заново: /start")
    await callback.answer()

@dp.callback_query(F.data == "step_back")
async def process_back(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    # Логика возврата на предыдущий шаг
    state_steps = [Form.name_age, Form.param_1, Form.param_2, Form.param_3, Form.why_me_or_about]
    current_index = state_steps.index(current_state)
    
    if current_index == 0:
        await state.clear()
        await callback.message.edit_text("Вы вернулись в главное меню.", reply_markup=main_kb())
    else:
        prev_state = state_steps[current_index - 1]
        await state.set_state(prev_state)
        data = await state.get_data()
        
        # Динамический текст вопросов в зависимости от роли
        questions = {
            Form.name_age: "1️⃣ Введите ваше реальное имя и возраст (например: Иван, 16):",
            Form.param_1: "2️⃣ Введите ваш игровой ник (Ivan_Ivanov):" if data['role'] == 'helper' else "2️⃣ Сколько времени проводите в Discord?",
            Form.param_2: "3️⃣ Ваш суточный онлайн (в часах):" if data['role'] == 'helper' else "3️⃣ Оцените знание правил Discord (от 0 до 10):",
            Form.param_3: "4️⃣ Опишите ваш опыт работы хелпером:" if data['role'] == 'helper' else "4️⃣ Опишите ваш опыт модерации Discord:"
        }
        await callback.message.edit_text(questions[prev_state], reply_markup=control_kb(show_back=(prev_state != Form.name_age)))
    await callback.answer()

# --- НАЧАЛО ОПРОСА ---
@dp.callback_query(F.data.in_({"start_helper", "start_support"}))
async def start_form(callback: types.CallbackQuery, state: FSMContext):
    role = "helper" if callback.data == "start_helper" else "support"
    await state.update_data(role=role)
    await state.set_state(Form.name_age)
    await callback.message.edit_text("1️⃣ **Введите ваше реальное имя и возраст** (например: Иван, 16):", parse_mode="Markdown", reply_markup=control_kb(show_back=False))
    await callback.answer()

# --- ПОШАГОВЫЙ СБОР ДАННЫХ ---
@dp.message(Form.name_age)
async def process_name_age(message: types.Message, state: FSMContext):
    # Извлекаем числа из текста для проверки возраста
    ages = [int(s) for s in re.findall(r'\b\d+\b', message.text)]
    if ages and ages[0] < 14:
        await message.answer("⚠️ К сожалению, на проект требуются сотрудники от **14 лет**. Подрастите и приходите позже!")
        await state.clear()
        return

    await state.update_data(name_age=message.text)
    data = await state.get_data()
    await state.set_state(Form.param_1)
    
    text = "2️⃣ **Введите ваш игровой ник на BEST RUSSIA** (Ivan_Ivanov):" if data['role'] == 'helper' else "2️⃣ **Сколько времени в день вы проводите в Discord?**"
    await message.answer(text, parse_mode="Markdown", reply_markup=control_kb())

@dp.message(Form.param_1)
async def process_param_1(message: types.Message, state: FSMContext):
    await state.update_data(param_1=message.text)
    data = await state.get_data()
    await state.set_state(Form.param_2)
    
    text = "3️⃣ **Каков ваш суточный онлайн?** (например: 4 часа):" if data['role'] == 'helper' else "3️⃣ **Оцените ваше знание правил Discord от 0 до 10:**"
    await message.answer(text, parse_mode="Markdown", reply_markup=control_kb())

@dp.message(Form.param_2)
async def process_param_2(message: types.Message, state: FSMContext):
    await state.update_data(param_2=message.text)
    data = await state.get_data()
    await state.set_state(Form.param_3)
    
    text = "4️⃣ **Имеется ли опыт работы хелпером?** (Опишите подробно):" if data['role'] == 'helper' else "4️⃣ **Опишите ваш опыт модерации в Discord:**"
    await message.answer(text, parse_mode="Markdown", reply_markup=control_kb())

@dp.message(Form.param_3)
async def process_param_3(message: types.Message, state: FSMContext):
    await state.update_data(param_3=message.text)
    data = await state.get_data()
    await state.set_state(Form.why_me_or_about)
    
    text = "5️⃣ **Почему именно вы должны занять этот пост?**" if data['role'] == 'helper' else "5️⃣ **Расскажите немного о себе и своих качествах:**"
    await message.answer(text, parse_mode="Markdown", reply_markup=control_kb())

@dp.message(Form.why_me_or_about)
async def process_final(message: types.Message, state: FSMContext):
    await state.update_data(why_me_or_about=message.text)
    data = await state.get_data()
    await state.clear()
    
    await message.answer("🚀 **Ваша заявка успешно отправлена! Ожидайте вердикта администрации в ЛС.**", parse_mode="Markdown")
    
    # Формируем красивый текст для админов
    role_title = "ХЕЛПЕР" if data['role'] == 'helper' else "АГЕНТ ПОДДЕРЖКИ"
    admin_text = (
        f"📥 **НОВАЯ ЗАЯВКА: {role_title}**\n\n"
        f"👤 **Кандидат:** {message.from_user.mention} (ID: `{message.from_user.id}`)\n"
        f"📝 **Имя и возраст:** {data['name_age']}\n"
        f"🔹 **Ник / Время в ДС:** {data['param_1']}\n"
        f"🔹 **Онлайн / Знание правил:** {data['param_2']}\n"
        f"💼 **Опыт работы:** {data['param_3']}\n"
        f"❓ **О себе / Почему он:** {data['why_me_or_about']}"
    )
    
    await bot.send_message(
        chat_id=ADMIN_CHAT_ID, 
        text=admin_text, 
        parse_mode="Markdown", 
        reply_markup=admin_decision_kb(message.from_user.id, data['role'])
    )

# --- ОБРАБОТКА РЕШЕНИЙ АДМИНИСТРАЦИИ ---
@dp.callback_query(AdminDecision.filter())
async def handle_admin_decision(callback: types.CallbackQuery, callback_data: AdminDecision):
    user_id = callback_data.user_id
    role_name = "Хелпера" if callback_data.role == "helper" else "Агента Поддержки"
    
    # Обновляем сообщение в админ-чате, чтобы убрать кнопки и зафиксировать результат
    old_text = callback.message.text
    
    if callback_data.action == "accept":
        new_text = f"✅ **ЗАЯВКА ОДОБРЕНА** администратором @{callback.from_user.username}\n\n{old_text}"
        user_text = f"🎉 Поздравляем! Ваша заявка на пост **{role_name}** проекта BEST RUSSIA одобрена!\nС вами свяжется администратор."
    else:
        new_text = f"❌ **ЗАЯВКА ОТКЛОНЕНА** администратором @{callback.from_user.username}\n\n{old_text}"
        user_text = f"😔 К сожалению, ваша заявка на пост **{role_name}** проекта BEST RUSSIA была отклонена."

    try:
        # Отправляем вердикт пользователю в ЛС
        await bot.send_message(chat_id=user_id, text=user_text)
    except Exception:
        new_text += "\n\n⚠️ *Бот не смог написать пользователю в ЛС (заблокирован или закрыт профиль)*"

    await callback.message.edit_text(text=new_text, reply_markup=None)
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
