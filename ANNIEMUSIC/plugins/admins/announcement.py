import os
import asyncio
import random
from datetime import datetime
from pyrogram import filters
from pyrogram.errors import FloodWait, ChatWriteForbidden
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

from ANNIEMUSIC import app  # ✅ gunakan instance utama bot

# === LOG LOAD ===
print("✅ Plugin announcement.py loaded successfully")

# === KONFIGURASI ===
LOGGER_ID = int(os.environ.get("LOGGER_ID", "-4812620726"))  # Grup log bot
MONGO_URL = os.environ.get("MONGO_DB_URI")
DB_NAME = "Annie"
COLLECTION_NAME = "chats"

# User ID admin / developer (gunakan @userinfobot untuk dapatkan ID)
SUDO_USERS = [7633980954]

# FOTO DEFAULT UNTUK PENGUMUMAN
ANNOUNCE_PHOTO_URL = (
    "https://raw.githubusercontent.com/mmahsunaz-eng/Onlyforachabot/"
    "623909aba0de9f88ed8756c71ab53ac7af878e35/ANNIEMUSIC/assets/"
    "file_00000000e5e462088641d9a6402214ca.png"
)

# === SETUP MONGO ===
mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]
chats_col = db[COLLECTION_NAME]

# === SIMPAN PESAN SEMENTARA ===
pending_announcements = {}


# === FUNGSI UTAMA /announce ===
@app.on_message(filters.command("announce") & filters.user(SUDO_USERS))
async def announce_preview(client, message):
    if len(message.command) < 2:
        return await message.reply_text("❗ Gunakan format:\n`/announce <pesan>`")

    user_text = message.text.split(None, 1)[1].strip()
    now = datetime.now()
    bulan = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
        5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
        9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    tanggal_str = f"{now.day} {bulan[now.month]} {now.year}"

    caption = (
        "```\n"
        "           🚨⚠️  ＰＥＮＧＵＭＵＭＡＮ ⚠️🚨\n"
        "```\n"
        "📣 **𝐏𝐄𝐌𝐁𝐄𝐑𝐈𝐓𝐀𝐇𝐔𝐀𝐍 𝐊𝐄𝐏𝐀𝐃𝐀 𝐏𝐀𝐑𝐀 𝐔𝐒𝐄𝐑 𝐁𝐎𝐓**\n\n"
        f"📅 **{tanggal_str}**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 {user_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💠 **Diterbitkan oleh:** ᴏꜰꜰɪᴄɪᴀʟ 「 Oɴʟʏғᴏʀᴀᴄʜᴀ ✘ ʙᴏᴛ 」\n"
        "💎 Tetap semangat dan terus nikmati musik bersama kami 🎶"
    )

    pending_announcements[message.from_user.id] = caption

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Kirim", callback_data="confirm_send"),
                InlineKeyboardButton("❌ Batal", callback_data="cancel_send"),
            ]
        ]
    )

    await message.reply_photo(
        photo=ANNOUNCE_PHOTO_URL,
        caption=caption,
        reply_markup=keyboard,
    )


# === HANDLER KONFIRMASI ===
@app.on_callback_query(filters.regex("^(confirm_send|cancel_send)$"))
async def confirm_announcement(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in pending_announcements:
        return await callback_query.answer("Tidak ada pengumuman aktif.", show_alert=True)

    caption = pending_announcements[user_id]

    if callback_query.data == "cancel_send":
        del pending_announcements[user_id]
        return await callback_query.message.edit_caption(
            caption + "\n\n❌ **Dibatalkan oleh admin.**"
        )

    if callback_query.data == "confirm_send":
        await callback_query.answer("Mengirim ke semua grup...", show_alert=False)
        sent, failed = 0, 0
        all_chats = list(chats_col.find({"chat_id": {"$lt": 0}}))
        total = len(all_chats)

        if total == 0:
            del pending_announcements[user_id]
            return await callback_query.message.edit_caption(
                caption + "\n\n⚠️ Tidak ada grup terdaftar di database."
            )

        admin_name = callback_query.from_user.mention
        start_time = datetime.now().strftime("%H:%M:%S")
        await client.send_message(
            LOGGER_ID,
            f"📢 **Broadcast dimulai**\n"
            f"👤 Oleh: {admin_name}\n"
            f"🕒 Waktu: {start_time}\n"
            f"💬 Total grup: {total}\n\n"
            f"Pesan:\n{caption[:1000]}"
        )

        status_msg = await client.send_message(LOGGER_ID, f"📢 Mengirim ke {total} grup...")

        for index, chat in enumerate(all_chats, start=1):
            chat_id = chat["chat_id"]
            try:
                await client.send_photo(chat_id, photo=ANNOUNCE_PHOTO_URL, caption=caption)
                sent += 1
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except ChatWriteForbidden:
                chats_col.delete_one({"chat_id": chat_id})
                failed += 1
            except Exception:
                failed += 1

            if index % 10 == 0 or index == total:
                percent = (index / total) * 100
                try:
                    await status_msg.edit_text(
                        f"📣 **Broadcast berjalan...**\n\n"
                        f"✅ Berhasil: {sent}\n"
                        f"❌ Gagal: {failed}\n"
                        f"📊 Progress: {index}/{total} grup ({percent:.1f}%)"
                    )
                except Exception:
                    pass

            await asyncio.sleep(random.uniform(1.2, 2.5))

        end_time = datetime.now().strftime("%H:%M:%S")
        try:
            await status_msg.edit_text(
                f"✅ **Broadcast selesai!**\n\n"
                f"📬 Berhasil: {sent}\n"
                f"❌ Gagal: {failed}\n"
                f"🕒 Selesai: {end_time}"
            )
        except Exception:
            pass

        await client.send_message(
            LOGGER_ID,
            f"✅ **Broadcast selesai!**\n"
            f"👤 Oleh: {callback_query.from_user.mention}\n"
            f"📬 Berhasil: {sent}\n"
            f"❌ Gagal: {failed}\n"
            f"🕒 Waktu selesai: {end_time}"
        )

        del pending_announcements[user_id]


# === AUTO ADD GROUP ===
@app.on_message(filters.new_chat_members)
async def auto_add_group(client, message):
    chat_id = message.chat.id
    if chat_id < 0:
        chats_col.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)


# === HELP MENU ===
__MODULE__ = "Announcement"
__HELP__ = """
**📣 Pengumuman untuk Admin:**

Gunakan perintah ini untuk mengirim pesan pengumuman ke semua grup yang sudah terdaftar di database.

**Perintah:**
/announce <pesan>  
Contoh:
`/announce Bot telah diupdate ke versi baru 🚀`

Bot akan menampilkan preview terlebih dahulu sebelum pengumuman dikirim.
"""
