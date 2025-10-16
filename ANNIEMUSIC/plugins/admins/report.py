import asyncio
from datetime import datetime, timedelta
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import os
from motor.motor_asyncio import AsyncIOMotorClient

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

    # === DESAIN LAPORAN DITERIMA ===
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

    # Simpan ke RAM
    pending_reports[sent.id] = {
        "user_id": reporter_id,
        "chat_id": chat_id,
        "chat_name": chat_name,
        "time": datetime.now(),
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
                    "created_at": datetime.utcnow(),
                }
            )
        except Exception as e:
            print(f"[MongoDB] Gagal menyimpan laporan: {e}")

    # Update tombol dinamis
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

    # Kirim notifikasi ke admin
    admins = await fetch_admins(client)
    for admin in admins:
        try:
            await client.send_photo(
                admin.id,
                photo=LOGO_URL,
                caption=caption,
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

    await message.reply_text(
        "✅ Laporan kamu telah dikirim ke tim admin.\nMohon tunggu, masalah kamu akan segera ditangani."
    )


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

    # === Jika Ditandai Selesai ===
    if action == "done":
        if info["solved"]:
            return await callback_query.answer("Laporan ini sudah selesai.", show_alert=True)
        info["solved"] = True

        # Update MongoDB
        if reports_col:
            try:
                await reports_col.update_one({"log_msg_id": log_msg_id}, {"$set": {"solved": True}})
            except Exception:
                pass

        # Update di log
        try:
            log_msg = await client.get_messages(LOGGER_ID, log_msg_id)
            await client.edit_message_caption(
                LOGGER_ID,
                log_msg_id,
                caption=log_msg.caption
                + f"\n\n✅ <b>Masalah diselesaikan oleh:</b> {admin.mention}"
            )
        except Exception:
            pass

        # Kirim notifikasi ke pelapor
        try:
            await client.send_photo(
                info["user_id"],
                photo=LOGO_URL,
                caption=(
                    "✅ <b>Masalah Kamu Telah Diselesaikan!</b>\n\n"
                    f"🏷️ <b>Grup/Channel:</b> {info['chat_name']}\n"
                    f"🪪 <b>ID:</b> <code>{info['chat_id']}</code>\n"
                    f"👨‍💻 <b>Ditangani oleh:</b> {admin.mention}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "💠 <b>Pesan ini dikirim oleh:</b> ᴏꜰꜰɪᴄɪᴀʟ 「 Oɴʟʏғᴏʀᴀᴄʜᴀ ✘ ʙᴏᴛ 」"
                ),
            )
        except Exception:
            pass

        await callback_query.answer("✅ Laporan ditandai selesai.", show_alert=True)
        return

    # === Jika Balas via Bot ===
    if action == "reply":
        await callback_query.answer("💬 Kirim pesan balasanmu sekarang...", show_alert=False)
        prompt_msg = await callback_query.message.reply_text(
            f"💬 {admin.mention}, kirim balasanmu untuk pelapor.\n⏳ Waktu 2 menit."
        )

        try:
            response = await client.listen(callback_query.message.chat.id, timeout=120)
        except asyncio.TimeoutError:
            await prompt_msg.edit_text("⌛ Waktu habis. Tidak ada pesan balasan dikirim.")
            return

        if not getattr(response, "text", None):
            return await prompt_msg.edit_text("❌ Hanya pesan teks yang dapat dikirim.")

        # === Desain Balasan Admin ===
        reply_caption = (
            "📬 <b>ＢＡＬＡＳＡＮ ＤＡＲＩ ＡＤＭＩＮ</b> 💬\n\n"
            f"{response.text}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 <b>Dikirim oleh:</b> {admin.mention}\n"
            "💠 <b>Melalui:</b> ᴏꜰꜰɪᴄɪᴀʟ 「 Oɴʟʏғᴏʀᴀᴄʜᴀ ✘ ʙᴏᴛ 」"
        )

        try:
            await client.send_photo(info["user_id"], photo=LOGO_URL, caption=reply_caption)
            await prompt_msg.edit_text("✅ Balasan berhasil dikirim ke pelapor.")
        except Exception as e:
            await prompt_msg.edit_text(f"⚠️ Gagal mengirim balasan: {e}")


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

            if reports_col:
                try:
                    await reports_col.delete_one({"log_msg_id": msg_id})
                except Exception:
                    pass

        # === Ringkasan Harian Jam 22:00 WIB (15:00 UTC) ===
        if now.hour == 15 and now.minute == 0:
            summary = (
                "🕘 <b>ＲＩＮＧＫＡＳＡＮ ＨＡＲＩＡＮ</b> 🕙\n\n"
                f"📅 <b>{now.strftime('%d %B %Y | %H:%M WIB')}</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📥 <b>Total Laporan:</b> {total}\n"
                f"✅ <b>Diselesaikan:</b> {solved}\n"
                f"⌛ <b>Kedaluwarsa:</b> {expired_count}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
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
**📣 Fitur Report Admin (Auto & MongoDB)**
• /report <masalah> → Kirim laporan ke admin
• Auto PM admin + log laporan
• Balasan admin via bot langsung ke pelapor
• Tandai selesai laporan
• Auto hapus laporan 24 jam
• Ringkasan harian otomatis jam 22.00 WIB
"""
