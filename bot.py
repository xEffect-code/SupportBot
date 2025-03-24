import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from dotenv import load_dotenv
from storage import get_or_create_alias, get_user_by_alias

# Загрузка токена и ID чата админов
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM-состояния для ручного ответа
class ReplyState(StatesGroup):
    waiting_for_text = State()

# Временное хранилище — кто кому отвечает
admin_reply_targets = {}

# Быстрые шаблоны
quick_replies = [
    "Пожалуйста, уточните ваш вопрос 😊",
    "Мы проверим и вернёмся с ответом 🔍",
    "Ваше обращение принято в обработку ✅"
]

# Клавиатура под каждым сообщением от пользователя (без кнопки Удалить)
def get_reply_keyboard(alias):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✍️ Ответить", callback_data=f"reply_to:{alias}"),
                InlineKeyboardButton(text="🔁 Быстрый ответ", callback_data=f"quick_reply:{alias}")
            ]
        ]
    )

# ✅ Приветствие по /start
@dp.message(Command("start"))
async def handle_start(message: types.Message):
    alias = get_or_create_alias(message.from_user.id)
    text = (
        f"👋 Привет, {alias}!\n\n"
        "Ты написал(-а) в поддержку.\n"
        "Просто напиши свой вопрос или сообщение сюда, и наши админы скоро ответят тебе 💬"
    )
    await message.answer(text)

# ✅ Сообщения от пользователя → в чат админов
@dp.message(F.chat.id != ADMIN_CHAT_ID)
async def handle_user_message(message: types.Message):
    user_id = message.from_user.id
    alias = get_or_create_alias(user_id)
    header = f"**{alias}**\n"
    sent = False

    # Текст
    if message.text:
        await bot.send_message(ADMIN_CHAT_ID, header + message.text, parse_mode="Markdown", reply_markup=get_reply_keyboard(alias))
        sent = True
    # Медиа
    elif message.photo:
        await bot.send_photo(ADMIN_CHAT_ID, message.photo[-1].file_id, caption=header, parse_mode="Markdown", reply_markup=get_reply_keyboard(alias))
        sent = True
    elif message.document:
        await bot.send_document(ADMIN_CHAT_ID, message.document.file_id, caption=header, parse_mode="Markdown", reply_markup=get_reply_keyboard(alias))
        sent = True
    elif message.video:
        await bot.send_video(ADMIN_CHAT_ID, message.video.file_id, caption=header, parse_mode="Markdown", reply_markup=get_reply_keyboard(alias))
        sent = True
    elif message.voice:
        await bot.send_voice(ADMIN_CHAT_ID, message.voice.file_id, caption=header, parse_mode="Markdown", reply_markup=get_reply_keyboard(alias))
        sent = True

    if not sent:
        await bot.send_message(ADMIN_CHAT_ID, header + "📎 Неизвестный формат.", parse_mode="Markdown", reply_markup=get_reply_keyboard(alias))

# ✍️ Ответить вручную
@dp.callback_query(F.data.startswith("reply_to:"))
async def handle_reply_button(callback: CallbackQuery, state: FSMContext):
    alias = callback.data.split(":", 1)[1]
    user_id = get_user_by_alias(alias)

    if not user_id:
        await callback.message.answer("❌ Пользователь не найден.")
        await callback.answer()
        return

    admin_reply_targets[callback.from_user.id] = user_id
    await state.set_state(ReplyState.waiting_for_text)
    await callback.message.answer(f"✍️ Напиши, что отправить пользователю с псевдонимом **{alias}**", parse_mode="Markdown")
    await callback.answer()

@dp.message(ReplyState.waiting_for_text)
async def process_admin_reply(message: types.Message, state: FSMContext):
    admin_id = message.from_user.id
    user_id = admin_reply_targets.get(admin_id)

    if not user_id:
        await message.reply("⚠️ Ошибка: не удалось найти пользователя.")
        await state.clear()
        return

    try:
        await bot.send_message(user_id, f"💬 Ответ поддержки:\n{message.text}")
        await message.reply("✅ Сообщение отправлено.")
    except Exception:
        await message.reply("⚠️ Не удалось отправить сообщение.")

    await state.clear()
    del admin_reply_targets[admin_id]

# 🔁 Быстрый ответ
@dp.callback_query(F.data.startswith("quick_reply:"))
async def handle_quick_reply(callback: CallbackQuery):
    alias = callback.data.split(":", 1)[1]
    user_id = get_user_by_alias(alias)

    if not user_id:
        await callback.message.answer("❌ Пользователь не найден.")
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(text=msg[:40], callback_data=f"send_quick:{user_id}:{i}")]
        for i, msg in enumerate(quick_replies)
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer("📌 Выбери шаблон для быстрого ответа:", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("send_quick:"))
async def send_quick_reply(callback: CallbackQuery):
    parts = callback.data.split(":")
    user_id = int(parts[1])
    index = int(parts[2])

    if index >= len(quick_replies):
        await callback.answer("⚠️ Шаблон не найден.")
        return

    try:
        await bot.send_message(user_id, f"💬 Ответ поддержки:\n{quick_replies[index]}")
        await callback.message.answer("✅ Быстрый ответ отправлен.")
    except Exception:
        await callback.message.answer("⚠️ Ошибка при отправке.")
    await callback.answer()

# Старт
async def on_startup(dp: Dispatcher):
    await bot.send_message(ADMIN_CHAT_ID, "🤖 Бот поддержки запущен!")

async def main():
    await on_startup(dp)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
