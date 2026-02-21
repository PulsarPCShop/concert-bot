import os
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import logging
import asyncio

logging.basicConfig(level=logging.INFO)

# ========== ТВОИ ДАННЫЕ (ВСТАВЬ СЮДА) ==========
BOT_TOKEN = "7604561890:AAHX1xJHECoWZfpUrRPHRlN9YxL-KriFiQs"  # <- ВСТАВЬ СВОЙ ТОКЕН
ADMIN_ID = 8598508284  # <- ВСТАВЬ СВОЙ ID (ТОЛЬКО ЦИФРЫ)
SECRET_KEY = "Creed2026"  # <- ТВОЙ КЛЮЧ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ
# =============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== БАЗА ДАННЫХ ==========
conn = sqlite3.connect('tickets.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
               (id INTEGER PRIMARY KEY, user_id TEXT UNIQUE, fio TEXT, ticket_number TEXT, date TEXT)''')
conn.commit()

# ========== СОСТОЯНИЯ ==========
class States(StatesGroup):
    wait_key = State()
    wait_fio = State()

# ========== СЧЁТЧИК БИЛЕТОВ ==========
def get_next_ticket_number():
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    # Начинаем с 268: первый билет будет 268, второй 269 и т.д.
    return f"№{268 + count:04d}"

# ========== ГЕНЕРАЦИЯ БИЛЕТА ==========
async def create_ticket(fio, ticket_num):
    # ОТКРОЕМ ШАБЛОН
    img = Image.open('template.png')
    draw = ImageDraw.Draw(img)
    
    # ШРИФТ
    font = ImageFont.truetype("arialmt.ttf", 40)
    
    # КООРДИНАТЫ ДЛЯ НОМЕРА (ПОТОМ ИЗМЕНИМ)
    draw.text((338, 500), ticket_num, fill="White", font=font)
    
    # СОХРАНЯЕМ
    path = f"tickets/{ticket_num}.png"
    os.makedirs("tickets", exist_ok=True)
    img.save(path)
    return path

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
    await state.set_state(States.wait_key)
    await msg.answer("🔑 Введи ключ для получения билета:")

@dp.message(States.wait_key)
async def check_key(msg: types.Message, state: FSMContext):
    if msg.text == SECRET_KEY:
        await state.update_data(key=msg.text)
        await state.set_state(States.wait_fio)
        await msg.answer("✅ Ключ верный! Введи свои ФИО:")
    else:
        await msg.answer("❌ Неверный ключ. Попробуй ещё раз:")

@dp.message(States.wait_fio)
async def get_fio(msg: types.Message, state: FSMContext):
    fio = msg.text.strip()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (str(msg.from_user.id),))
    if cursor.fetchone():
        await msg.answer("❌ Ты уже получил билет!")
        await state.clear()
        return
    
    ticket_num = get_next_ticket_number()
    
    try:
        path = await create_ticket(fio, ticket_num)
        
        cursor.execute("INSERT INTO users (user_id, fio, ticket_number, date) VALUES (?, ?, ?, ?)",
                      (str(msg.from_user.id), fio, ticket_num, datetime.now().strftime("%d.%m.%Y %H:%M")))
        conn.commit()
        
        with open(path, 'rb') as photo:
            await msg.answer_photo(
                types.input_file.BufferedInputFile(photo.read(), filename=f"билет{ticket_num}.png"),
                caption=f"🎫 ТВОЙ БИЛЕТ {ticket_num}\n👤 {fio}"
            )
        
        await bot.send_message(ADMIN_ID, f"🎫 Новый билет!\n👤 {fio}\n🎟 {ticket_num}")
        
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")
    
    await state.clear()

# ========== АДМИНКА ==========
@dp.message(Command("admin"))
async def admin_panel(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT fio, ticket_number, date FROM users ORDER BY id DESC LIMIT 5")
    last = cursor.fetchall()
    
    text = f"📊 **СТАТИСТИКА**\nВсего билетов: {total}\n\n"
    if last:
        text += "**Последние:**\n"
        for fio, num, date in last:
            text += f"• {num} - {fio} ({date})\n"
    
    await msg.answer(text, parse_mode="Markdown")

@dp.message(Command("list"))
async def list_tickets(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    
    cursor.execute("SELECT fio, ticket_number FROM users ORDER BY id")
    all_users = cursor.fetchall()
    
    if not all_users:
        await msg.answer("📭 Пока нет билетов")
        return
    
    text = "🎫 **ВСЕ БИЛЕТЫ:**\n"
    for fio, num in all_users:
        text += f"{num} - {fio}\n"
    
    await msg.answer(text)

# ========== ЗАПУСК ==========
async def main():
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())