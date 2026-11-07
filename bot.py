
import asyncio
import sqlite3
import os
import html

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# =========================
# SOZLAMALAR
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

PRIVATE_CHANNEL_ID = os.getenv("PRIVATE_CHANNEL_ID", "")
PRIVATE_CHANNEL_ID = int(PRIVATE_CHANNEL_ID) if PRIVATE_CHANNEL_ID else None

PUBLIC_CHANNEL = os.getenv(
    "PUBLIC_CHANNEL",
    "@ujas_kino_tarjima"
)

POST_CHANNEL = os.getenv(
    "POST_CHANNEL",
    "@ujas_kino_tarjima"
)

if not BOT_TOKEN or not ADMIN_ID:
    raise RuntimeError("BOT_TOKEN va ADMIN_ID sozlanmagan!")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# =========================
# DATABASE
# =========================

db = sqlite3.connect("movies.db")
db.execute("""
CREATE TABLE IF NOT EXISTS movies (
    code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    file_id TEXT NOT NULL
)
""")
db.commit()


def get_movie(code):
    return db.execute(
        "SELECT code, title, description, file_id FROM movies WHERE code=?",
        (code,)
    ).fetchone()


def save_movie(code, title, description, file_id):
    db.execute(
        "INSERT INTO movies VALUES (?, ?, ?, ?)",
        (code, title, description, file_id)
    )
    db.commit()


def delete_movie(code):
    cursor = db.execute(
        "DELETE FROM movies WHERE code=?",
        (code,)
    )
    db.commit()
    return cursor.rowcount > 0


# =========================
# MAJBURIY OBUNA
# =========================

async def check_subscription(user_id):
    if PRIVATE_CHANNEL_ID is None:
        return False

    channels = [
        PRIVATE_CHANNEL_ID,
        PUBLIC_CHANNEL
    ]

    for channel in channels:
        try:
            member = await bot.get_chat_member(
                chat_id=channel,
                user_id=user_id
            )

            if member.status not in ("member", "administrator", "creator"):
                return False

        except Exception as error:
            print("Obuna tekshirish xatosi:", error)
            return False

    return True


def subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="1-kanalga obuna bo‘lish",
                url="https://t.me/+HKP31UIW3Dk4Y2Fi"
            )
        ],
        [
            InlineKeyboardButton(
                text="2-kanalga obuna bo‘lish",
                url="https://t.me/ujas_kino_tarjima"
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Obunani tekshirish",
                callback_data="check_sub"
            )
        ]
    ])


async def require_subscription(message, user_id):
    if await check_subscription(user_id):
        return True

    await message.answer(
        "🎬 Kinolarni ko‘rish uchun quyidagi kanallarga "
        "obuna bo‘ling!\n\n"
        "Obuna bo‘lgach, tekshirish tugmasini bosing.",
        reply_markup=subscription_keyboard()
    )
    return False


# =========================
# ADMIN PANEL
# =========================

def is_admin(user_id):
    return user_id == ADMIN_ID


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Kino qo‘shish",
                callback_data="add_movie"
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑 Kino o‘chirish",
                callback_data="delete_movie"
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Kino statistikasi",
                callback_data="movie_stats"
            )
        ]
    ])


@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "⚙️ <b>ADMIN PANEL</b>\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=admin_keyboard()
    )


# =========================
# KINO QO‘SHISH FSM
# =========================

class AddMovie(StatesGroup):
    video = State()
    title = State()
    description = State()
    code = State()


class DeleteMovie(StatesGroup):
    code = State()


@dp.callback_query(F.data == "add_movie")
async def add_movie_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo‘q!", show_alert=True)
        return

    await state.set_state(AddMovie.video)
    await callback.message.answer(
        "🎥 Kinoning videosini yuboring:"
    )
    await callback.answer()


@dp.message(AddMovie.video, F.video)
async def get_movie_video(message: Message, state: FSMContext):
    await state.update_data(file_id=message.video.file_id)
    await state.set_state(AddMovie.title)

    await message.answer("📝 Kino nomini yuboring:")


@dp.message(AddMovie.video)
async def wrong_video(message: Message):
    await message.answer("Iltimos, kino videosini yuboring.")


@dp.message(AddMovie.title)
async def get_movie_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddMovie.description)

    await message.answer("📄 Kino haqida qisqacha ma'lumot yuboring:")


@dp.message(AddMovie.description)
async def get_movie_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddMovie.code)

    await message.answer("🔢 Kino uchun maxsus kod kiriting:")


@dp.message(AddMovie.code)
async def get_movie_code(message: Message, state: FSMContext):
    code = (message.text or "").strip()

    if not code.isdigit():
        await message.answer("Kod faqat raqamlardan iborat bo‘lsin.")
        return

    if get_movie(code):
        await message.answer("Bu kod allaqachon mavjud. Boshqa kod kiriting.")
        return

    data = await state.get_data()

    try:
        save_movie(
            code,
            data["title"],
            data["description"],
            data["file_id"]
        )

        me = await bot.get_me()
        watch_url = f"https://t.me/{me.username}?start=m_{code}"

        post_text = (
            f"🎬 <b>{html.escape(data['title'])}</b>\n\n"
            f"{html.escape(data['description'])}\n\n"
            f"🔢 Kino kodi: <code>{code}</code>\n\n"
            f"🍿 Kinoni ko‘rish uchun pastdagi tugmani bosing!"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎬 KINONI KO‘RISH",
                    url=watch_url
                )
            ]
        ])

        await bot.send_message(
            chat_id=POST_CHANNEL,
            text=post_text,
            reply_markup=keyboard
        )

        await message.answer(
            f"✅ Kino saqlandi va kanalga joylandi!\n\n"
            f"🎬 Nomi: {html.escape(data['title'])}\n"
            f"🔢 Kodi: <code>{code}</code>"
        )

    except Exception as error:
        print("Kino joylash xatosi:", error)
        await message.answer(
            "Kino bazaga saqlandi, ammo kanalga joylashda xatolik yuz berdi. "
            "Botning kanal adminligini tekshiring."
        )

    await state.clear()


# =========================
# KINO O‘CHIRISH
# =========================

@dp.callback_query(F.data == "delete_movie")
async def delete_movie_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo‘q!", show_alert=True)
        return

    await state.set_state(DeleteMovie.code)
    await callback.message.answer("O‘chiriladigan kino kodini yuboring:")
    await callback.answer()


@dp.message(DeleteMovie.code)
async def delete_movie_finish(message: Message, state: FSMContext):
    code = (message.text or "").strip()

    if delete_movie(code):
        await message.answer("✅ Kino o‘chirildi.")
    else:
        await message.answer("❌ Bunday kodli kino topilmadi.")

    await state.clear()


# =========================
# STATISTIKA
# =========================

@dp.callback_query(F.data == "movie_stats")
async def movie_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo‘q!", show_alert=True)
        return

    count = db.execute(
        "SELECT COUNT(*) FROM movies"
    ).fetchone()[0]

    await callback.message.answer(
        f"📊 Bazadagi kinolar soni: <b>{count}</b>"
    )
    await callback.answer()


# =========================
# KINO YUBORISH
# =========================

async def send_movie(target, code):
    movie = get_movie(code)

    if not movie:
        await target.answer("❌ Bunday kino kodi topilmadi.")
        return

    _, title, description, file_id = movie

    caption = (
        f"🎬 <b>{html.escape(title)}</b>\n\n"
        f"{html.escape(description or '')}\n\n"
        f"🍿 Yoqimli tomosha!"
    )

    await target.answer_video(
        video=file_id,
        caption=caption
    )


# =========================
# START
# =========================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    if not await require_subscription(message, message.from_user.id):
        return

    args = message.text.split(maxsplit=1)

    if len(args) > 1 and args[1].startswith("m_"):
        code = args[1][2:]
        await send_movie(message, code)
        return

    await message.answer(
        "🎬 <b>KINO BOTGA XUSH KELIBSIZ!</b>\n\n"
        "Bu bot orqali sevimli kinolaringizni tomosha qilishingiz mumkin.\n\n"
        "🔢 Kinoni ko‘rish uchun uning kodini yuboring.\n\n"
        "🍿 Yoqimli tomosha!"
    )


# =========================
# OBUNANI QAYTA TEKSHIRISH
# =========================

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.edit_text(
            "✅ Obuna tasdiqlandi!\n\n"
            "🎬 Endi kino kodini yuborishingiz mumkin."
        )
        await callback.answer("Obuna tasdiqlandi!")
    else:
        await callback.answer(
            "Ikkala kanalga ham obuna bo‘ling!",
            show_alert=True
        )


# =========================
# KINO KODINI QABUL QILISH
# =========================

@dp.message(F.text)
async def movie_by_code(message: Message):
    if not await require_subscription(message, message.from_user.id):
        return

    code = message.text.strip()

    if code.isdigit():
        await send_movie(message, code)
    else:
        await message.answer(
            "🔢 Iltimos, kino kodini yuboring."
        )


# =========================
# ISHGA TUSHIRISH
# =========================

async def main():
    print("Kino bot ishga tushdi!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
  
