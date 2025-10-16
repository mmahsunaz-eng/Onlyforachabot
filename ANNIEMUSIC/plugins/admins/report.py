import asyncio
from datetime import datetime, timedelta, timezone
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import os
from motor.motor_asyncio import AsyncIOMotorClient
from ANNIEMUSIC import app

# === KONFIGURASI ===
LOGGER_ID = int(os.environ.get("LOGGER_ID", "-4812620726"))
LOGO_URL = (
    "https://raw.githubusercontent.com/mmahsunaz-eng/Onlyforachabot/"
    "623909aba0de9f88ed8756c71ab53ac7af878e35/ANNIEMUSIC/assets/"
    "file_00000000e5e462088641d9a6402214ca.png"
)
MONGO_URL = os.getenv("MONGO_DB_URI", None)

# Zona waktu Surabaya (WIB)
WIB = timezone(timedelta(hours=7))

# === KONEKSI MONGO ===
mongo_client = AsyncIOMotorClient(MONGO_URL) if MONGO_URL else None
db = mongo_client["Annie"] if mongo_client else None
reports_col = db["reports"] if db is not None else None

# === PENYIMPANAN SEMENTARA ===
pending_reports = {}

# === HELPERS ===
async def safe_get_chat_name(client, chat):
    if chat is None:
        return "Unknown"
    if getattr(chat, "title", None):
        return chat.title
    if getattr(chat, "username", None):
        return f"@{chat.username}"
    if getattr(chat, "first_name", None):
        name = chat.first_name
        if getattr(chat, "last_name", None):
            name += f" {chat.last_name}"
        return name
    return "Private Chat"


async def fetch_admins(client):
    admins = []
    try:
        async for member in client.get_chat_members(LOGGER_ID, filter="administrators"):
            if not member.user.is_bot:
                admins.append(member.user)
    except Exception:
        return []
    return admins


# === COMMAND /report ===
@app.on_message(filters.command("report"))
async def report_issue(client, message):
    if len(message.command) < 2:
        return await message.reply_text("❗ Gunakan format:\n`/report <masalah>`")

    problem = message.text.split(None, 1)[1]
    report_time = datetime.now(WIB).strftime("%d %B %Y | %H:%M WIB")

    reporter = message.from_user or message.sender_chat
    reporter_repr = f"{reporter.mention if hasattr(reporter, 'mention') else reporter.title} (`{reporter.id}`)"
    reporter_id = reporter.id

    chat = message.chat
    chat_name = await safe_get_chat_name(client, chat)
    chat_id = chat.id

    caption = (
        "🚨⚠️ <b>ＰＥＲＨＡＴＩＡＮ</b> ⚠️🚨\n\n"
        "<b>Laporan Masalah Baru Telah Diterima!</b>\n\n"
        f"👤 <b>Pelapor:</b> {reporter_repr}\n"
        f"💬 <b>Masalah:</b> <i>{problem}</i>\n"
        f"🏷️ <b>Asal:</b> {chat_name}\n"
        f"🪪 <b>ID Asal:</b> <code>{chat_id}</code>\n"
        f"🕒 <b>{report_time}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💠 <b>Diterima oleh:</b> ᴏꜰꜰɪᴄɪᴀʟ 「 Oɴʟʏғᴏʀᴀᴄʜᴀ ✘ ʙᴏᴛ 」"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔁 Balas via Bot", callback_data="reply_pending"),
                InlineKeyboardButton("✅ Tandai Selesai", callback_data="done_pending"),
            ]
        ]
    )

    try:
        sent = await client.send_photo(LOGGER_ID, photo=LOGO_URL, caption=caption, reply_markup=keyboard)
    except Exception as e:
        return await message.reply_text(f"⚠️ Gagal kirim laporan ke log: {e}")

    pending_reports[sent.id] = {
        "user_id": reporter_id,
        "chat_id": chat_id,
        "chat_name": chat_name,
        "problem": problem,
        "time": datetime.now(WIB),
        "solved": False,
    }

    # Simpan ke MongoDB
    if reports_col:
        try:
            await reports_col.insert_one(
                {
                    "log_msg_id": sent.id,
                    "user_id": reporter_id,
                    "chat_id": chat_id,
                    "chat_name": chat_name,
                    "problem": problem,
                    "solved": False,
                    "created_at": datetime.now(WIB),
                }
            )
        except Exception as e:
            print(f"[MongoDB] Gagal menyimpan laporan: {e}")

    # Kirim notifikasi ke tiap admin
    admins = await fetch_admins(client)
    for admin in admins:
        try:
            await client.send_photo(
                admin.id,
                photo=LOGO_URL,
                caption=(
                    f"🚨 <b>Laporan Baru Masuk!</b>\n\n"
                    f"👤 Dari: {reporter_repr}\n"
                    f"💬 Masalah: <i>{problem}</i>\n"
                    f"🏷️ Grup/Channel: {chat_name}\n"
                    f"🪪 ID Grup/Channel: <code>{chat_id}</code>\n"
                    f"🕒 {report_time}\n\n"
                    "Klik tombol di bawah untuk membalas."
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("🔁 Balas via Bot", callback_data=f"reply_{sent.id}"),
                            InlineKeyboardButton("✅ Tandai Selesai", callback_data=f"done_{sent.id}"),
                        ]
                    ]
                ),
            )
        except Exception:
            continue

    await message.reply_text("✅ Laporan telah dikirim ke tim admin. Mohon tunggu responnya.")


# === AKTIVASI TOMBOL ===
@app.on_callback_query(filters.regex(r"^(reply_|done_)pending$"))
async def handle_pending_action(client, callback_query: CallbackQuery):
    log_msg_id = callback_query.message.id
    new_kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔁 Balas via Bot", callback_data=f"reply_{log_msg_id}"),
                InlineKeyboardButton("✅ Tandai Selesai", callback_data=f"done_{log_msg_id}"),
            ]
        ]
    )
    try:
        await client.edit_message_reply_markup(LOGGER_ID, log_msg_id, reply_markup=new_kb)
    except Exception:
        pass
    await callback_query.answer("✅ Tombol diaktifkan.", show_alert=False)


# === SISTEM BALASAN DENGAN /reply ===
reply_context = {}  # {admin_id: log_msg_id}

@app.on_callback_query(filters.regex(r"^reply_\d+$"))
async def prepare_reply(client, callback_query: CallbackQuery):
    admin = callback_query.from_user
    log_msg_id = int(callback_query.data.split("_")[1])

    if log_msg_id not in pending_reports:
        return await callback_query.answer("❌ Laporan tidak ditemukan.", show_alert=True)

    reply_context[admin.id] = log_msg_id
    await client.send_message(
        admin.id,
        "💬 Silakan kirim balasanmu dengan format:\n\n"
        "<code>/reply Pesan balasan kamu</code>\n\n"
        "Contoh:\n<code>/reply Sudah kami tangani, terima kasih.</code>",
    )
    await callback_query.answer("📩 Silakan kirim /reply di DM bot.", show_alert=False)


@app.on_message(filters.command("reply") & filters.private)
async def admin_reply(client, message):
    admin_id = message.from_user.id
    if admin_id not in reply_context:
        return await message.reply_text("❗ Kamu belum memilih laporan untuk dibalas.\nKlik dulu tombol 🔁 di pesan laporan.")

    log_msg_id = reply_context[admin_id]
    info = pending_reports.get(log_msg_id)
    if not info:
        return await message.reply_text("⚠️ Laporan sudah tidak tersedia atau kadaluarsa.")

    reply_text = message.text.split(None, 1)[1] if len(message.command) > 1 else None
    if not reply_text:
        return await message.reply_text("❗ Gunakan format:\n`/reply <pesan>`")

    text_to_send = (
        f"💬 <b>Balasan dari Admin:</b>\n\n"
        f"{reply_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 <b>Admin:</b> {message.from_user.mention}\n"
        f"👤 <b>Untuk Pelapor:</b> <a href='tg://user?id={info['user_id']}'>Pelapor</a>"
    )

    # kirim ke grup pelapor
    try:
        await client.send_photo(info["chat_id"], photo=LOGO_URL, caption=text_to_send)
    except Exception as e:
        await message.reply_text(f"⚠️ Gagal kirim ke grup pelapor: {e}")
        return

    # kirim ke DM pelapor
    try:
        await client.send_photo(info["user_id"], photo=LOGO_URL, caption=text_to_send)
    except Exception:
        pass

    # update log
    try:
        old = await client.get_messages(LOGGER_ID, log_msg_id)
        new_caption = (old.caption or "") + f"\n\n💬 <b>Dibalas oleh:</b> {message.from_user.mention}"
        await client.edit_message_caption(LOGGER_ID, log_msg_id, caption=new_caption)
    except Exception:
        pass

    del reply_context[admin_id]
    await message.reply_text("✅ Balasan berhasil dikirim ke pelapor dan grup asal.")


# === PENANDA SELESAI ===
@app.on_callback_query(filters.regex(r"^done_\d+$"))
async def mark_done(client, callback_query: CallbackQuery):
    admin = callback_query.from_user
    log_msg_id = int(callback_query.data.split("_")[1])

    info = pending_reports.get(log_msg_id)
    if not info:
        return await callback_query.answer("❌ Laporan tidak ditemukan.", show_alert=True)

    if info["solved"]:
        return await callback_query.answer("Sudah diselesaikan.", show_alert=True)

    info["solved"] = True
    if reports_col:
        try:
            await reports_col.update_one({"log_msg_id": log_msg_id}, {"$set": {"solved": True}})
        except Exception:
            pass

    try:
        old = await client.get_messages(LOGGER_ID, log_msg_id)
        new_caption = (old.caption or "") + f"\n\n✅ <b>Masalah diselesaikan oleh:</b> {admin.mention}"
        await client.edit_message_caption(LOGGER_ID, log_msg_id, caption=new_caption)
    except Exception:
        pass

    try:
        await client.send_photo(
            info["user_id"],
            photo=LOGO_URL,
            caption=(
                "✅ <b>Laporan Kamu Telah Diselesaikan!</b>\n\n"
                f"🏷️ Grup/Channel: {info['chat_name']}\n"
                f"🪪 ID Grup/Channel: <code>{info['chat_id']}</code>\n"
                f"👨‍💻 <b>Ditangani oleh:</b> {admin.mention}\n\n"
                "Terima kasih telah melapor 💙"
            ),
        )
    except Exception:
        pass

    await callback_query.answer("✅ Laporan ditandai selesai.", show_alert=True)


# === AUTO CLEAN + RINGKASAN 22:00 WIB ===
async def auto_clean_reports(client):
    while True:
        total, solved, expired = 0, 0, 0
        expired_ids = []

        for msg_id, info in list(pending_reports.items()):
            total += 1
            if info.get("solved"):
                solved += 1
            if datetime.now(WIB) - info["time"] > timedelta(hours=24):
                expired_ids.append(msg_id)

        for msg_id in expired_ids:
            try:
                await client.delete_messages(LOGGER_ID, msg_id)
            except Exception:
                pass
            pending_reports.pop(msg_id, None)
            expired += 1
            if reports_col:
                try:
                    await reports_col.delete_one({"log_msg_id": msg_id})
                except Exception:
                    pass

        wib_now = datetime.now(WIB)
        if wib_now.hour == 22 and wib_now.minute == 0:
            summary = (
                "🕙 <b>RINGKASAN HARIAN — Onlyforacha ✘ Bot</b>\n"
                f"📅 <b>{wib_now.strftime('%d %B %Y | %H:%M WIB')}</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📥 <b>Total Laporan:</b> {total}\n"
                f"✅ <b>Diselesaikan:</b> {solved}\n"
                f"⌛ <b>Kedaluwarsa (24 jam):</b> {expired}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "📡 <b>Status:</b> Stabil ✅"
            )
            try:
                await client.send_message(LOGGER_ID, summary)
            except Exception as e:
                print(f"[SummaryError] {e}")
            await asyncio.sleep(60)

        await asyncio.sleep(60)


__MODULE__ = "Admin"
__HELP__ = """
**📣 Fitur Report Admin (vFinal — Timezone Surabaya / WIB)**

- `/report <masalah>` → Kirim laporan ke grup log & admin.
- Admin klik 🔁 lalu DM bot dengan `/reply <pesan>` untuk membalas.
- Balasan otomatis dikirim ke grup asal & DM pelapor.
- Admin juga bisa klik ✅ untuk menandai laporan selesai.
- Auto hapus laporan lama (24 jam) + Ringkasan harian 22:00 WIB.
"""
