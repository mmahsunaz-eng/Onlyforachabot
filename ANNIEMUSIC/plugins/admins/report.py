import asyncio
from datetime import datetime, timedelta
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import os
from motor.motor_asyncio import AsyncIOMotorClient

from ANNIEMUSIC import app

# === KONFIGURASI ===
LOGGER_ID = int(os.environ.get("LOGGER_ID", "-4812620726"))
LOGO_URL = "https://raw.githubusercontent.com/mmahsunaz-eng/Onlyforachabot/623909aba0de9f88ed8756c71ab53ac7af878e35/ANNIEMUSIC/assets/file_00000000e5e462088641d9a6402214ca.png"
MONGO_URL = os.getenv("MONGO_URL", None)

# === KONEKSI MONGODB ===
mongo_client = AsyncIOMotorClient(MONGO_URL) if MONGO_URL else None
db = mongo_client["ANNIEMUSIC"] if mongo_client else None
reports_col = db["reports"] if db else None

# === PENYIMPANAN SEMENTARA ===
pending_reports = {}
active_reply = {}       # admin_id -> log_msg_id
pending_preview = {}    # admin_id -> message_id (preview)

# === HELPERS ===
async def safe_get_chat_name(client, chat):
    if chat is None:
        return "Unknown"
    if getattr(chat, "title", None):
        return chat.title
    if getattr(chat, "username", None):
        return f"@{chat.username}"
    name = "Private Chat"
    if getattr(chat, "first_name", None):
        name = chat.first_name
        if getattr(chat, "last_name", None):
            name += f" {chat.last_name}"
    return name


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
        return await message.reply_text(
            "❗ Gunakan format:\n/report <masalah>"
        )

    problem = message.text.split(None, 1)[1]
    report_time = datetime.now().strftime("%d %B %Y | %H:%M WIB")

    if message.from_user:
        reporter = message.from_user
        reporter_repr = f"{reporter.mention} ({reporter.id})"
        reporter_id = reporter.id
    else:
        sender = message.sender_chat
        reporter_repr = f"{sender.title} (channel) ({sender.id})"
        reporter_id = sender.id

    chat = message.chat
    chat_name = await safe_get_chat_name(client, chat)
    chat_id = chat.id

    caption = (
        "🚨⚠️ PERHATIAN ⚠️🚨\n\n"
        "Laporan Masalah Baru Telah Diterima!\n\n"
        f"👤 Pelapor: {reporter_repr}\n"
        f"💬 Masalah: {problem}\n"
        f"🏷️ Asal: {chat_name}\n"
        f"🪪 ID Asal: {chat_id}\n"
        f"🕒 {report_time}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💠 Diterima oleh: Onlyforacha ✘ Bot"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔁 Balas via Bot", callback_data=f"reply_{reporter_id}"),
                InlineKeyboardButton("✅ Tandai Selesai", callback_data=f"done_{reporter_id}"),
            ]
        ]
    )

    try:
        sent = await client.send_photo(LOGGER_ID, photo=LOGO_URL, caption=caption, reply_markup=keyboard)
    except Exception as e:
        return await message.reply_text(f"⚠️ Gagal mengirim laporan ke log: {e}")

    pending_reports[sent.id] = {
        "user_id": reporter_id,
        "chat_id": chat_id,
        "chat_name": chat_name,
        "time": datetime.now(),
        "solved": False,
        "report_msg_id": message.id,
        "problem": problem,
        "reporter_repr": reporter_repr
    }

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
                    "created_at": datetime.utcnow(),
                }
            )
        except Exception as e:
            print(f"[MongoDB] Gagal menyimpan laporan: {e}")

    await message.reply_text("✅ Laporan kamu telah dikirim ke tim admin onlyforachabot.\nMohon tunggu, masalah kamu akan segera ditangani.")


# === CALLBACK HANDLER ===
@app.on_callback_query(filters.regex(r"^(reply_|done_)\d+"))
async def handle_report_action(client, callback_query: CallbackQuery):
    data = callback_query.data
    admin = callback_query.from_user
    action, rest = data.split("_", 1)
    key = int(rest) if rest.isdigit() else None

    report_info = None
    for msg_id, info in pending_reports.items():
        if info["user_id"] == key:
            report_info = info
            report_info["log_msg_id"] = msg_id
            break

    if not report_info:
        return await callback_query.answer("Laporan tidak ditemukan atau sudah kadaluwarsa.", show_alert=True)

    if action == "done":
        report_info["solved"] = True
        try:
            await client.send_photo(
                report_info["chat_id"],
                photo=LOGO_URL,
                caption=(
                    "✅💠 LAPORAN SELESAI 💠✅\n\n"
                    f"Laporan Kamu Telah Diselesaikan!\n\n"
                    f"🏷️ Grup/Channel: {report_info['chat_name']}\n"
                    f"👨‍💻 Ditangani oleh: {admin.mention}\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "💙 Terima kasih telah melapor!"
                ),
                reply_to_message_id=report_info.get("report_msg_id"),
            )
        except Exception:
            pass
        return await callback_query.answer("✅ Ditandai selesai.", show_alert=True)

    if action == "reply":
        active_reply[admin.id] = report_info["log_msg_id"]
        await callback_query.message.reply_text(
            f"💬 {admin.first_name}, untuk membalas laporan ini ketik:\n/reply [pesan balasan]"
        )
        await callback_query.answer("Instruksi dikirim!", show_alert=False)


# === COMMAND /reply ===
@app.on_message(filters.command("reply"))
async def manual_reply_to_report(client, message):
    admin_id = message.from_user.id
    if admin_id not in active_reply:
        return await message.reply_text(
            "❌ Kamu belum memilih laporan.\nTekan dulu tombol “Balas via Bot”."
        )

    if len(message.command) < 2:
        return await message.reply_text("❗ Gunakan format:\n/reply [pesan balasan]")

    reply_text = message.text.split(None, 1)[1]
    log_msg_id = active_reply[admin_id]
    info = pending_reports.get(log_msg_id)
    if not info:
        return await message.reply_text("⚠️ Laporan tidak ditemukan atau sudah kadaluwarsa.")

    preview_caption = (
        "📬 Preview Balasan\n\n"
        f"{reply_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💠 Dikirim oleh: {message.from_user.mention}"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Kirim", callback_data=f"send_reply_{admin_id}"),
                InlineKeyboardButton("❌ Batal", callback_data=f"cancel_reply_{admin_id}")
            ]
        ]
    )

    sent = await message.reply_text(preview_caption, reply_markup=keyboard)
    pending_preview[admin_id] = {
        "msg_id": sent.id,
        "text": reply_text,
        "info": info
    }


# === CALLBACK untuk konfirmasi kirim / batal ===
@app.on_callback_query(filters.regex(r"^(send_reply_|cancel_reply_)\d+"))
async def confirm_reply_action(client, callback_query: CallbackQuery):
    data = callback_query.data
    action, admin_id = data.split("_", 1)
    admin_id = int(admin_id)
    admin = callback_query.from_user

    preview = pending_preview.get(admin_id)
    if not preview:
        return await callback_query.answer("⚠️ Tidak ada balasan yang menunggu konfirmasi.", show_alert=True)

    info = preview["info"]

    if action == "cancel":
        try:
            await callback_query.message.delete()
        except Exception:
            pass
        pending_preview.pop(admin_id, None)
        active_reply.pop(admin_id, None)
        return await callback_query.answer("❌ Balasan dibatalkan.", show_alert=True)

    if action == "send":
        try:
            await client.send_photo(
                info["chat_id"],
                photo=LOGO_URL,
                caption=(
                    "📬 Balasan dari Admin:\n\n"
                    f"{preview['text']}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💠 Dikirim oleh: {admin.mention}"
                ),
                reply_to_message_id=info.get("report_msg_id"),
            )
            await callback_query.message.edit_text("✅ Balasan berhasil dikirim ke grup pelapor.")
        except Exception as e:
            await callback_query.message.edit_text(f"⚠️ Gagal mengirim balasan: {e}")

        pending_preview.pop(admin_id, None)
        active_reply.pop(admin_id, None)
        await callback_query.answer("✅ Balasan terkirim!", show_alert=True)


# === AUTO CLEANUP ===
async def auto_clean_reports(client):
    while True:
        expired_ids = []
        for msg_id, info in list(pending_reports.items()):
            if datetime.now() - info["time"] > timedelta(hours=24):
                expired_ids.append(msg_id)
        for msg_id in expired_ids:
            try:
                await client.delete_messages(LOGGER_ID, msg_id)
            except Exception:
                pass
            pending_reports.pop(msg_id, None)
        await asyncio.sleep(60)


__MODULE__ = "Admin"
__HELP__ = """
📣 Fitur Report Admin (Auto & MongoDB)

- /report <masalah>
  Kirim laporan ke grup log & admin.

- /reply [pesan]
  Tampilkan preview balasan dan konfirmasi sebelum dikirim.
"""
