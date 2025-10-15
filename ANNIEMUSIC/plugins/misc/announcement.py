import os
import asyncio
import random
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, ChatWriteForbidden
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

# === KONFIGURASI ===
LOGGER_ID = int(os.environ.get("LOGGER_ID", "-4812620726"))  # 💬 Grup log bot kamu
MONGO_URL = os.environ.get("MONGO_DB_URI")
DB_NAME = "Annie"
COLLECTION_NAME = "chats"

# === FOTO DEFAULT UNTUK PENGUMUMAN ===
ANNOUNCE_PHOTO_URL = (
    "https://raw.githubusercontent.com/mmahsunaz-eng/Onlyforachabot/"
    "623909aba0de9f88ed8756c71ab53ac7af878e35/ANNIEMUSIC/assets/"
    "file_00000000e5e462088641d9a6402214ca.png"
)

# === SETUP MONGO ===
mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]
chats_col = db[COLLECTION_NAME]

# === SIMPAN PESAN SEMENTARA (untuk konfirmasi kirim) ===
pending_announcements = {}


# === FUNGSI PENGUMUMAN ===
@Client.on_message(filters.command("announce") & filters.chat(LOGGER_ID))
async def announce_preview(_, message):
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

    # simpan pengumuman ke memory sementara
    pending_announcements[message.from_user.id] = caption

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Kirim", callback_data="confirm_send"),
                InlineKeyboardButton("❌ Batal", callback_data="cancel_send"),
            ]
        ]
    )

    await _.send_photo(
        LOGGER_ID,
        photo=ANNOUNCE_PHOTO_URL,
        caption=caption,
        reply_markup=keyboard,
    )


# === HANDLER KONFIRMASI ===
@Client.on_callback_query(filters.chat(LOGGER_ID))
async def confirm_announcement(_, callback_query):
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
            return await callback_query.message.edit_caption(
                caption + "\n\n⚠️ Tidak ada grup terdaftar di database."
            )

        status_msg = await _.send_message(LOGGER_ID, f"📢 Mengirim ke {total} grup...")

        for index, chat in enumerate(all_chats, start=1):
            chat_id = chat["chat_id"]
            try:
                await _.send_photo(chat_id, photo=ANNOUNCE_PHOTO_URL, caption=caption)
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

        try:
            await status_msg.edit_text(
                f"✅ **Broadcast selesai!**\n\n"
                f"📬 Berhasil: {sent}\n"
                f"❌ Gagal: {failed}\n"
                f"🕒 Selesai: {datetime.now().strftime('%H:%M:%S')}"
            )
        except Exception:
            await _.send_message(LOGGER_ID, f"✅ Broadcast selesai. Berhasil: {sent} | Gagal: {failed}")

        # hapus dari pending
        del pending_announcements[user_id]


# === AUTO ADD GRUP ===
@Client.on_message(filters.new_chat_members)
async def auto_add_group(_, message):
    chat_id = message.chat.id
    if chat_id < 0:
        chats_col.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)
