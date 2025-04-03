import os
import asyncio
from collections import defaultdict
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InputMediaPhoto, InputMediaVideo
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from storage import get_or_create_alias

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
OWNER_ID = int(os.getenv("OWNER_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

message_map = {}
known_users = set()
user_info = {}

user_media_groups = defaultdict(list)
admin_media_groups = defaultdict(list)
media_group_timers = {}

@dp.message(Command("start"))
async def handle_start(message: Message):
    alias = get_or_create_alias(message.from_user.id)
    text = (
        f"👋 Привет, {alias}!\n\n"
        "Ты написал(-а) в поддержку. Просто опиши свой вопрос — и мы ответим как можно скорее 💬"
    )
    await message.answer(text)

@dp.message(Command("users"))
async def handle_users_command(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    if not user_info:
        await message.answer("📭 Нет пользователей.")
        return

    lines = ["👥 Пользователи:\n"]
    for uid, data in user_info.items():
        username = f"@{data['username']}" if data['username'] else "(без username)"
        alias = data["alias"]
        lines.append(f"• {username} — {alias} (ID: {uid})")

    await message.answer("\n".join(lines))

@dp.message(F.chat.type == "private")
async def handle_user_message(message: Message):
    if not message.from_user.username:
        await message.answer(
            "❗ Чтобы воспользоваться ботом поддержки, пожалуйста, установи @username в настройках Telegram.\n\n"
        )
        return

    user_id = message.from_user.id
    username = message.from_user.username
    alias = get_or_create_alias(user_id)
    caption = message.caption or ""

    user_info[user_id] = {"alias": alias, "username": username}
    send_to_owner = user_id not in known_users
    if send_to_owner:
        known_users.add(user_id)

    id_or_username = f"@{username}"
    header = f"**{alias}**\n{caption}"
    header_with_id = f"**{alias} ({id_or_username})**\n{caption}"

    if message.media_group_id:
        user_media_groups[message.media_group_id].append((message, alias, username, send_to_owner))
        if message.media_group_id not in media_group_timers:
            media_group_timers[message.media_group_id] = asyncio.create_task(
                process_user_album(message.media_group_id)
            )
        return

    await forward_single_message(message, alias, header, header_with_id, user_id, username, send_to_owner)

async def forward_single_message(message, alias, header, header_with_id, user_id, username, send_to_owner=True):
    forwarded = None

    if message.text:
        forwarded = await bot.send_message(ADMIN_CHAT_ID, f"**{alias}**\n{message.text}", parse_mode="Markdown")
        if send_to_owner:
            await bot.send_message(OWNER_ID, header_with_id, parse_mode="Markdown")

    elif message.photo:
        forwarded = await bot.send_photo(ADMIN_CHAT_ID, message.photo[-1].file_id, caption=header, parse_mode="Markdown")
        if send_to_owner:
            await bot.send_photo(OWNER_ID, message.photo[-1].file_id, caption=header_with_id, parse_mode="Markdown")

    elif message.document:
        forwarded = await bot.send_document(ADMIN_CHAT_ID, message.document.file_id, caption=header, parse_mode="Markdown")
        if send_to_owner:
            await bot.send_document(OWNER_ID, message.document.file_id, caption=header_with_id, parse_mode="Markdown")

    elif message.voice:
        forwarded = await bot.send_voice(ADMIN_CHAT_ID, message.voice.file_id, caption=header, parse_mode="Markdown")
        if send_to_owner:
            await bot.send_voice(OWNER_ID, message.voice.file_id, caption=header_with_id, parse_mode="Markdown")

    elif message.video:
        forwarded = await bot.send_video(ADMIN_CHAT_ID, message.video.file_id, caption=header, parse_mode="Markdown")
        if send_to_owner:
            await bot.send_video(OWNER_ID, message.video.file_id, caption=header_with_id, parse_mode="Markdown")

    elif message.sticker:
        forwarded = await bot.send_sticker(ADMIN_CHAT_ID, message.sticker.file_id)
        if send_to_owner:
            await bot.send_sticker(OWNER_ID, message.sticker.file_id)

    if forwarded:
        message_map[forwarded.message_id] = user_id

async def process_user_album(media_group_id):
    await asyncio.sleep(1.5)
    group = user_media_groups.pop(media_group_id, [])
    if not group:
        return

    user_id = group[0][0].from_user.id
    alias = group[0][1]
    username = group[0][2]
    send_to_owner = group[0][3]
    id_or_username = f"@{username}"

    media_admin = []
    media_owner = []

    for i, (msg, _, _, _) in enumerate(group):
        cap = msg.caption or ""
        cap_with_alias = f"**{alias}**\n{cap}" if i == 0 else None
        cap_with_id = f"**{alias} ({id_or_username})**\n{cap}" if i == 0 else None

        if msg.photo:
            media_admin.append(InputMediaPhoto(media=msg.photo[-1].file_id, caption=cap_with_alias, parse_mode="Markdown"))
            media_owner.append(InputMediaPhoto(media=msg.photo[-1].file_id, caption=cap_with_id, parse_mode="Markdown"))
        elif msg.video:
            media_admin.append(InputMediaVideo(media=msg.video.file_id, caption=cap_with_alias, parse_mode="Markdown"))
            media_owner.append(InputMediaVideo(media=msg.video.file_id, caption=cap_with_id, parse_mode="Markdown"))

    if media_admin:
        sent = await bot.send_media_group(ADMIN_CHAT_ID, media_admin)
        for s in sent:
            message_map[s.message_id] = user_id
        if send_to_owner:
            sent_owner = await bot.send_media_group(OWNER_ID, media_owner)
            for s in sent_owner:
                message_map[s.message_id] = user_id

@dp.message(F.chat.id.in_({ADMIN_CHAT_ID, OWNER_ID}))
async def handle_admin_reply(message: Message):
    if not message.reply_to_message:
        return

    media_group_id = message.media_group_id
    if media_group_id:
        admin_media_groups[media_group_id].append(message)
        if media_group_id not in media_group_timers:
            media_group_timers[media_group_id] = asyncio.create_task(
                process_admin_album(media_group_id, message.reply_to_message.message_id)
            )
        return

    await process_admin_reply(message, message.reply_to_message.message_id)

async def process_admin_album(media_group_id, original_message_id):
    await asyncio.sleep(1.5)
    group = admin_media_groups.pop(media_group_id, [])
    user_id = message_map.get(original_message_id)
    if not user_id:
        return

    media = []
    for i, msg in enumerate(group):
        cap = msg.caption or ""
        if msg.photo:
            media.append(InputMediaPhoto(media=msg.photo[-1].file_id, caption=f"💬 Поддержка:\n{cap}" if i == 0 else None))
        elif msg.video:
            media.append(InputMediaVideo(media=msg.video.file_id, caption=f"💬 Поддержка:\n{cap}" if i == 0 else None))

    if media:
        await bot.send_media_group(user_id, media)
        conf = await group[-1].reply("✅ Отправлено пользователю.")
        await asyncio.sleep(3)
        await conf.delete()

async def process_admin_reply(message: Message, original_id: int):
    user_id = message_map.get(original_id)
    if not user_id:
        await message.reply("⚠️ Не удалось определить, кому ответить.")
        return

    try:
        text = message.text or message.caption or ""

        if message.text:
            await bot.send_message(user_id, f"💬 Поддержка:\n{text}")
        elif message.photo:
            await bot.send_photo(user_id, message.photo[-1].file_id, caption=f"💬 Поддержка:\n{text}")
        elif message.document:
            await bot.send_document(user_id, message.document.file_id, caption=f"💬 Поддержка:\n{text}")
        elif message.voice:
            await bot.send_voice(user_id, message.voice.file_id, caption="💬 Поддержка")
        elif message.video:
            await bot.send_video(user_id, message.video.file_id, caption=f"💬 Поддержка:\n{text}")
        elif message.sticker:
            await bot.send_sticker(user_id, message.sticker.file_id)
        else:
            await message.reply("⚠️ Тип контента пока не поддерживается.")

        confirmation = await message.reply("✅ Отправлено пользователю.")
        await asyncio.sleep(3)
        await confirmation.delete()
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при отправке: {e}")

async def main():
    await bot.send_message(ADMIN_CHAT_ID, "🤖 SupplierBot запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
