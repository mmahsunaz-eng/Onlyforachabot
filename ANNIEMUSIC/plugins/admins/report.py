import asyncio
from datetime import datetime, timedelta
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import os
from motor.motor_asyncio import AsyncIOMotorClient  # 🧩 untuk MongoDB

# pakai app utama dari ANNIEMUSIC
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
pending_reports = {}  # {log_msg_id: {"user_id": int, "chat_id": int, "chat_name": str, "time": datetime, "solved": bool}}

# === HELPERS ===
async def safe_get_chat_name(client, chat):
    """Kembalikan nama representatif untuk chat (grup/channel/private)."""
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
    """Kembalikan list User objek admin (exclude bot accounts)."""
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
        [
            [
                InlineKeyboardButton("🔁 Balas via Bot", callback_data=f"reply_pending"),
                InlineKeyboardButton("✅ Tandai Selesai", callback_data=f"done_pending"),
            ]
        ]
    )

    try:
        sent = await client.send_photo(
            LOGGER_ID,
            photo=LOGO_URL,
            caption=caption,
            reply_markup=keyboard,
        )
    except Exception as e:
        await message.reply_text(f"⚠️ Gagal mengirim laporan ke log: {e}")
        return

    # Simpan detail laporan ke RAM
    pending_reports[sent.id] = {
        "user_id": reporter_id,
        "chat_id": chat_id,
        "chat_name": chat_name,
        "time": datetime.now(),
        "solved": False,
    }

    # 🧩 Simpan juga ke MongoDB
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

    try:
        new_kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔁 Balas via Bot", callback_data=f"reply_{sent.id}"),
                    InlineKeyboardButton("✅ Tandai Selesai", callback_data=f"done_{sent.id}"),
                ]
            ]
        )
        await client.edit_message_reply_markup(LOGGER_ID, sent.id, reply_markup=new_kb)
    except Exception:
        pass

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

    await message.reply_text("✅ Laporan kamu telah dikirim ke tim admin.\nMohon tunggu, masalah kamu akan segera ditangani.")


# === CALLBACK HANDLER ===
@app.on_callback_query(filters.regex(r"^(reply_|done_)\d+"))
async def handle_report_action(client, callback_query: CallbackQuery):
    data = callback_query.data
    admin = callback_query.from_user

    try:
        action, rest = data.split("_", 1)
        log_msg_id = int(rest)
    except Exception:
        return await callback_query.answer("Data callback invalid.", show_alert=True)

    info = pending_reports.get(log_msg_id)
    if not info:
        return await callback_query.answer("Laporan tidak ditemukan atau sudah kadaluwarsa.", show_alert=True)

    if action == "done":
        if info["solved"]:
            return await callback_query.answer("Laporan ini sudah ditandai selesai.", show_alert=True)

        info["solved"] = True

        # Update di MongoDB juga
        if reports_col:
            try:
                await reports_col.update_one({"log_msg_id": log_msg_id}, {"$set": {"solved": True}})
            except Exception:
                pass

        try:
            await client.edit_message_caption(
                LOGGER_ID,
                log_msg_id,
                caption=(await client.get_messages(LOGGER_ID, log_msg_id)).caption
                + f"\n\n✅ <b>Masalah diselesaikan oleh:</b> {admin.mention}"
            )
        except Exception:
            pass

        try:
    await client.send_photo(
        info["user_id"],
        photo=LOGO_URL,
        caption=(
            "✅💠 <b>ＬＡＰＯＲＡＮ ＳＥＬＥＳＡＩ</b> 💠✅\n\n"
            "<b>Laporan Kamu Telah Diselesaikan!</b>\n\n"
            f"🏷️ <b>Grup/Channel:</b> {info['chat_name']}\n"
            f"🪪 <b>ID Grup/Channel:</b> <code>{info['chat_id']}</code>\n"
            f"👨‍💻 <b>Ditangani oleh:</b> {admin.mention}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💙 <b>Terima kasih telah melapor!</b>\n"
            "🙏 <i>Kami menghargai kontribusimu dalam menjaga komunitas tetap aman dan nyaman.</i>"
        )
    )  # ✅ ← tambahkan kurung tutup ini
except Exception:
    pass
        await callback_query.answer("✅ Laporan ditandai selesai.", show_alert=True)
        return

    if action == "reply":
        await callback_query.answer("💬 Kirim pesan balasanmu sekarang...", show_alert=False)
        prompt_msg = await callback_query.message.reply_text(
            f"💬 {admin.mention}, silakan kirim balasanmu untuk pelapor.\n⏳ Kamu punya waktu 2 menit."
        )
        try:
            response = await client.listen(callback_query.message.chat.id, timeout=120)
        except asyncio.TimeoutError:
            await prompt_msg.edit_text("⌛ Waktu habis. Tidak ada pesan balasan dikirim.")
            return

        if not getattr(response, "text", None):
            return await prompt_msg.edit_text("❌ Hanya pesan teks yang bisa dikirim.")

        try:
            await client.send_photo(
                info["user_id"],
                photo=LOGO_URL,
                caption=(
                    "📬 <b>Balasan dari Admin:</b>\n\n"
                    f"{response.text}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💠 <b>Dikirim oleh:</b> {admin.mention}"
                ),
            )
            await prompt_msg.edit_text("✅ Balasan berhasil dikirim ke pelapor.")
        except Exception as e:
            await prompt_msg.edit_text(f"⚠️ Gagal mengirim balasan ke pelapor: {e}")

# === COMMAND /reply ===
@app.on_message(filters.command("reply"))
async def manual_reply_to_report(client, message):
    if len(message.command) < 3:
        return await message.reply_text("❗ Gunakan format:\n`/reply <log_msg_id> <pesan>`")

    try:
        log_msg_id = int(message.command[1])
        reply_text = message.text.split(None, 2)[2]
    except Exception:
        return await message.reply_text("⚠️ Format salah. Contoh:\n`/reply 12345 Terima kasih, sudah kami tindaklanjuti.`")

    info = pending_reports.get(log_msg_id)
    if not info and reports_col:
        data = await reports_col.find_one({"log_msg_id": log_msg_id})
        if data:
            info = {"chat_id": data["chat_id"], "chat_name": data["chat_name"], "user_id": data["user_id"]}

    if not info:
        return await message.reply_text("❌ Laporan tidak ditemukan atau sudah kadaluwarsa.")

    chat_id = info["chat_id"]
    user_id = info["user_id"]
    admin = message.from_user

    try:
        chat_messages = await client.get_chat_history(chat_id, limit=10)
        reply_to_msg_id = next((msg.id for msg in chat_messages if msg.from_user and msg.from_user.id == user_id), None)

        await client.send_photo(
            chat_id,
            photo=LOGO_URL,
            caption=(
                "📬 <b>Balasan dari Admin:</b>\n\n"
                f"{reply_text}\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💠 <b>Dikirim oleh:</b> {admin.mention}"
            ),
            reply_to_message_id=reply_to_msg_id,
        )

        await message.reply_text(f"✅ Balasan dikirim ke grup asal laporan: <b>{info['chat_name']}</b>")
    except Exception as e:
        await message.reply_text(f"⚠️ Gagal mengirim balasan ke grup: {e}")

# === AUTO CLEANUP & DAILY SUMMARY ===
async def auto_clean_reports(client):
    while True:
        now = datetime.now()
        total, solved, expired_count = 0, 0, 0
        expired_ids = []

        for msg_id, info in list(pending_reports.items()):
            total += 1
            if info["solved"]:
                solved += 1
            if datetime.now() - info["time"] > timedelta(hours=24):
                expired_ids.append(msg_id)

        for msg_id in expired_ids:
            try:
                await client.delete_messages(LOGGER_ID, msg_id)
            except Exception:
                pass
            del pending_reports[msg_id]
            expired_count += 1

            # Hapus dari Mongo juga
            if reports_col:
                try:
                    await reports_col.delete_one({"log_msg_id": msg_id})
                except Exception:
                    pass

        if now.hour == 16 and now.minute == 59:
            summary = (
                "🕘 <b>Laporan Harian — Onlyforacha ✘ Bot</b>\n"
                f"📅 <b>{now.strftime('%d %B %Y | %H:%M WIB')}</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📥 <b>Laporan Masuk (saat cek):</b> {total}\n"
                f"✅ <b>Diselesaikan:</b> {solved}\n"
                f"⌛ <b>Kedaluwarsa (24 jam):</b> {expired_count}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "📡 <b>Status:</b> Stabil ✅\n"
                "💠 <b>Dikirim otomatis oleh:</b> ᴏꜰꜰɪᴄɪᴀʟ 「 Oɴʟʏғᴏʀᴀᴄʜᴀ ✘ ʙᴏᴛ 」"
            )
            try:
                await client.send_message(LOGGER_ID, summary)
            except Exception:
                pass

        await asyncio.sleep(60)


@app.on_message(filters.command("start"))
async def start_auto_task(client, message):
    asyncio.create_task(auto_clean_reports(client))
    await message.reply_text("✅ Sistem auto-clean & notifikasi admin aktif.")


__MODULE__ = "Admin"
__HELP__ = """
**📣 Fitur Report Admin (Auto & PM + MongoDB):**

/report <masalah>
Kirim laporan masalah langsung ke grup log & admin.

/reply <log_msg_id> <pesan>
Balas laporan langsung ke grup asal pelapor.

/start
Aktifkan auto-clean & notifikasi admin harian.
"""
