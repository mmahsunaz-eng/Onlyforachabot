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

# === KONEKSI MONGO ===
mongo_client = AsyncIOMotorClient(MONGO_URL) if MONGO_URL else None
db = mongo_client["ANNIEMUSIC"] if mongo_client else None
reports_col = db["reports"] if db else None

# === PENYIMPANAN SEMENTARA ===
pending_reports = {}  # {log_msg_id: {..., "pending_reply": {...}}}

# === HELPER ===
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
    report_time = datetime.now().strftime("%d %B %Y | %H:%M WIB")

    if message.from_user:
        reporter = message.from_user
        reporter_repr = f"{reporter.mention} (`{reporter.id}`)"
        reporter_id = reporter.id
    else:
        sender = message.sender_chat
        reporter_repr = f"{sender.title} (channel) (`{sender.id}`)"
        reporter_id = sender.id

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
        [[
            InlineKeyboardButton("🔁 Balas via Bot", callback_data="reply_pending"),
            InlineKeyboardButton("✅ Tandai Selesai", callback_data="done_pending"),
        ]]
    )

    try:
        sent = await client.send_photo(LOGGER_ID, photo=LOGO_URL, caption=caption, reply_markup=keyboard)
    except Exception as e:
        return await message.reply_text(f"⚠️ Gagal kirim laporan ke log: {e}")

    pending_reports[sent.id] = {
        "user_id": reporter_id,
        "chat_id": chat_id,
        "chat_name": chat_name,
        "time": datetime.now(),
        "solved": False,
    }

    if reports_col:
        try:
            await reports_col.insert_one({
                "log_msg_id": sent.id,
                "user_id": reporter_id,
                "chat_id": chat_id,
                "chat_name": chat_name,
                "problem": problem,
                "solved": False,
                "created_at": datetime.utcnow(),
            })
        except Exception as e:
            print(f"[MongoDB] Gagal menyimpan laporan: {e}")

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
                    "Gunakan tombol di bawah untuk menindaklanjuti."
                ),
                reply_markup=InlineKeyboardMarkup(
                    [[
                        InlineKeyboardButton("🔁 Balas via Bot", callback_data=f"reply_{sent.id}"),
                        InlineKeyboardButton("✅ Tandai Selesai", callback_data=f"done_{sent.id}"),
                    ]]
                ),
            )
        except Exception:
            continue

    await message.reply_text("✅ Laporan telah dikirim ke tim admin. Mohon tunggu responnya.")


# === HANDLER UNTUK PENDING ===
@app.on_callback_query(filters.regex(r"^(reply_|done_)pending$"))
async def handle_pending_action(client, callback_query: CallbackQuery):
    data = callback_query.data
    action = data.split("_", 1)[0]
    message = callback_query.message
    log_msg_id = message.id

    new_kb = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("🔁 Balas via Bot", callback_data=f"reply_{log_msg_id}"),
            InlineKeyboardButton("✅ Tandai Selesai", callback_data=f"done_{log_msg_id}"),
        ]]
    )
    try:
        await client.edit_message_reply_markup(LOGGER_ID, log_msg_id, reply_markup=new_kb)
    except Exception:
        pass
    await callback_query.answer("✅ Tombol diaktifkan.", show_alert=False)


# === HANDLER UTAMA (REPLY & DONE) ===
@app.on_callback_query(filters.regex(r"^(reply_|done_)\d+"))
async def handle_report_action(client, callback_query: CallbackQuery):
    data = callback_query.data
    admin = callback_query.from_user
    try:
        action, rest = data.split("_", 1)
        log_msg_id = int(rest)
    except Exception:
        return await callback_query.answer("Callback invalid.", show_alert=True)

    info = pending_reports.get(log_msg_id)
    if not info:
        return await callback_query.answer("❌ Laporan tidak ditemukan.", show_alert=True)

    if action == "done":
        if info["solved"]:
            return await callback_query.answer("Sudah diselesaikan.", show_alert=True)
        info["solved"] = True
        if reports_col:
            await reports_col.update_one({"log_msg_id": log_msg_id}, {"$set": {"solved": True}})
        await callback_query.answer("✅ Ditandai selesai.", show_alert=True)
        try:
            await client.send_photo(
                info["user_id"],
                photo=LOGO_URL,
                caption=(
                    "✅ <b>Laporan Kamu Telah Diselesaikan!</b>\n\n"
                    f"🏷️ Grup: {info['chat_name']}\n"
                    f"👨‍💻 <b>Admin:</b> {admin.mention}"
                ),
            )
        except Exception:
            pass
        return

    # === Balas via bot dengan konfirmasi ===
    await callback_query.answer("💬 Kirim balasanmu sekarang...", show_alert=False)
    prompt = await callback_query.message.reply_text(f"{admin.mention}, kirim teks balasanmu. ⏳ 2 menit.")
    try:
        from pyrogram import filters as flt
        response = await client.listen(flt.user(admin.id) & flt.text, timeout=120)
    except asyncio.TimeoutError:
        await prompt.edit_text("⌛ Waktu habis.")
        return
    reply_text = response.text
    confirm = await client.send_message(
        admin.id,
        f"📝 <b>Pratinjau:</b>\n\n{reply_text}\n\nKirim ke grup pelapor?",
        reply_markup=InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ Kirim", callback_data=f"confirm_send_{log_msg_id}"),
                InlineKeyboardButton("❌ Batal", callback_data=f"cancel_send_{log_msg_id}"),
            ]]
        ),
    )
    pending_reports[log_msg_id]["pending_reply"] = {
        "admin_id": admin.id,
        "text": reply_text,
        "confirm_msg_id": confirm.id,
    }


# === HANDLER KONFIRMASI KIRIM ===
@app.on_callback_query(filters.regex(r"^(confirm_send_|cancel_send_)\d+"))
async def handle_confirmation(client, callback_query: CallbackQuery):
    data = callback_query.data
    admin = callback_query.from_user
    action, msg_id = data.split("_", 1)
    log_msg_id = int(msg_id)

    info = pending_reports.get(log_msg_id)
    if not info or "pending_reply" not in info:
        return await callback_query.answer("Data tidak ditemukan.", show_alert=True)
    reply = info["pending_reply"]

    if reply["admin_id"] != admin.id:
        return await callback_query.answer("❌ Bukan balasan kamu.", show_alert=True)

    if action.startswith("cancel_send_"):
        await client.edit_message_text(admin.id, reply["confirm_msg_id"], "❌ Balasan dibatalkan.")
        del info["pending_reply"]
        return await callback_query.answer("Dibatalkan.", show_alert=True)

    text_to_send = (
        f"📬 <b>Balasan dari Admin:</b>\n\n{reply['text']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💠 <b>Dikirim oleh:</b> {admin.mention}\n"
        f"👤 <b>Untuk:</b> <a href='tg://user?id={info['user_id']}'>Pelapor</a>"
    )
    await client.send_photo(info["chat_id"], photo=LOGO_URL, caption=text_to_send)
    await client.edit_message_text(admin.id, reply["confirm_msg_id"], "✅ Balasan berhasil dikirim.")
    del info["pending_reply"]
    await callback_query.answer("Dikirim ke grup pelapor.", show_alert=False)


# === AUTO CLEAN + RINGKASAN HARIAN ===
async def auto_clean_reports(client):
    while True:
        now = datetime.now()
        total, solved, expired = 0, 0, 0

        expired_ids = []
        for msg_id, info in list(pending_reports.items()):
            total += 1
            if info.get("solved"):
                solved += 1
            if datetime.now() - info["time"] > timedelta(hours=24):
                expired_ids.append(msg_id)

        for msg_id in expired_ids:
            try:
                await client.delete_messages(LOGGER_ID, msg_id)
            except Exception:
                pass
            pending_reports.pop(msg_id, None)
            expired += 1
            if reports_col:
                await reports_col.delete_one({"log_msg_id": msg_id})

        # Kirim ringkasan jam 22:00 WIB (Zona Waktu Surabaya / Asia/Jakarta)
        from datetime import timezone, timedelta
        wib = datetime.now(timezone(timedelta(hours=7)))  # UTC+7
        if wib.hour == 22 and wib.minute == 0:
            summary = (
                "🕙 <b>RINGKASAN HARIAN — Onlyforacha ✘ Bot</b>\n"
                f"📅 <b>{wib.strftime('%d %B %Y | %H:%M WIB')}</b>\n"
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
            try:
                await client.send_message(LOGGER_ID, summary)
            except Exception:
                pass

        await asyncio.sleep(60)


@app.on_message(filters.command("start"))
async def start_auto_task(client, message):
    asyncio.create_task(auto_clean_reports(client))
    await message.reply_text("✅ Auto-clean & laporan harian aktif.")


__MODULE__ = "Admin"
__HELP__ = """
**📣 Fitur Report Admin (Lengkap + MongoDB + Konfirmasi + Ringkasan Harian)**

- `/report <masalah>` → kirim laporan ke log + admin
- Admin bisa balas via bot dengan konfirmasi ✅❌
- Balasan dikirim ke grup pelapor
- Tandai selesai sinkron MongoDB
- Auto hapus laporan lama (24 jam)
- Ringkasan harian jam 16:59 WIB
"""
