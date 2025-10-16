import asyncio
from datetime import datetime, timedelta, timezone
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.handlers import MessageHandler
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
MONGO_URL = os.getenv("MONGO_URL", None)

# === KONEKSI MONGO ===
mongo_client = AsyncIOMotorClient(MONGO_URL) if MONGO_URL else None
db = mongo_client["ANNIEMUSIC"] if mongo_client else None
reports_col = db["reports"] if db else None

# === PENYIMPANAN SEMENTARA ===
# Struktur:
# pending_reports = {
#   log_msg_id: {
#       "user_id": int,
#       "chat_id": int,
#       "chat_name": str,
#       "problem": str,
#       "time": datetime,
#       "solved": bool,
#       "pending_reply": {"admin_id": int, "text": str, "confirm_msg_id": int} (optional)
#   }
# }
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

    # Kirim notifikasi ke tiap admin (PM) dengan tombol yang sudah berisi id log
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
            # jika gagal kirim ke satu admin, lanjutkan admin lain
            continue

    await message.reply_text("✅ Laporan telah dikirim ke tim admin. Mohon tunggu responnya.")


# === AKTIVASI TOMBOL PENDING ===
@app.on_callback_query(filters.regex(r"^(reply_|done_)pending$"))
async def handle_pending_action(client, callback_query: CallbackQuery):
    # ubah markup pesan log (di LOGGER_ID) jadi tombol bereferensi id
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


# === HANDLER UTAMA: REPLY / DONE (menggunakan id) ===
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

    # === TANDAI SELESAI ===
    if action == "done":
        if info["solved"]:
            return await callback_query.answer("Sudah diselesaikan.", show_alert=True)
        info["solved"] = True
        if reports_col:
            try:
                await reports_col.update_one({"log_msg_id": log_msg_id}, {"$set": {"solved": True}})
            except Exception:
                pass
        try:
            # edit caption di log untuk menandai penyelesaian
            old_msg = await client.get_messages(LOGGER_ID, log_msg_id)
            new_caption = (old_msg.caption or "") + f"\n\n✅ <b>Masalah diselesaikan oleh:</b> {admin.mention}"
            await client.edit_message_caption(LOGGER_ID, log_msg_id, caption=new_caption)
        except Exception:
            pass

        # coba PM pelapor kalau bisa
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
        return

    # === REPLY: mulai proses tunggu pesan admin tanpa .listen() ===
    await callback_query.answer("💬 Kirim balasanmu sekarang (DM bot).", show_alert=False)

    prompt = await callback_query.message.reply_text(f"{admin.mention}, kirim teks balasanmu di DM bot. ⏳ 2 menit.")

    # akan menunggu pesan dari admin di private chat (chat.id == admin.id)
    future = asyncio.get_event_loop().create_future()

    async def _temp_msg_handler(c, m):
        try:
            # Pastikan pesan dari admin di private (DM) dan berupa teks
            if not m.from_user:
                return
            if m.from_user.id != admin.id:
                return
            if m.chat.id != admin.id:
                # hanya terima DM
                return
            if not getattr(m, "text", None):
                return
            if not future.done():
                future.set_result(m)
        except Exception:
            # jangan biarkan handler crash
            if not future.done():
                future.set_result(None)

    # buat MessageHandler sementara
    handler = MessageHandler(_temp_msg_handler, filters.user(admin.id) & filters.private & filters.text)
    client.add_handler(handler)

    try:
        response = await asyncio.wait_for(future, timeout=120)
        if response is None:
            await prompt.edit_text("❌ Terjadi kesalahan saat membaca balasan.")
            return
        reply_text = response.text
    except asyncio.TimeoutError:
        await prompt.edit_text("⌛ Waktu habis. Tidak ada balasan dikirim.")
        return
    finally:
        # selalu hapus handler sementara supaya tidak menumpuk
        try:
            client.remove_handler(handler)
        except Exception:
            pass

    # === PREVIEW & KONFIRMASI ===
    preview = (
        f"📝 <b>Pratinjau Balasan:</b>\n\n"
        f"{reply_text}\n\n"
        "Apakah ingin dikirim ke pelapor?"
    )
    try:
        confirm_msg = await client.send_message(
            admin.id,
            preview,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("✅ Kirim", callback_data=f"confirm_send_{log_msg_id}"),
                        InlineKeyboardButton("❌ Batal", callback_data=f"cancel_send_{log_msg_id}"),
                    ]
                ]
            ),
        )
    except Exception as e:
        await prompt.edit_text(f"⚠️ Gagal tampilkan preview: {e}")
        return

    # simpan pending reply pada laporan
    pending_reports[log_msg_id]["pending_reply"] = {
        "admin_id": admin.id,
        "text": reply_text,
        "confirm_msg_id": confirm_msg.id,
    }

    await prompt.edit_text("✅ Balasan diterima. Silakan konfirmasi pada preview di DM.")


# === KONFIRMASI KIRIM / BATAL ===
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
        return await callback_query.answer("❌ Kamu bukan pengirim balasan ini.", show_alert=True)

    # Batal
    if action.startswith("cancel_send_"):
        try:
            await client.edit_message_text(admin.id, reply["confirm_msg_id"], "❌ Balasan dibatalkan.")
        except Exception:
            pass
        del info["pending_reply"]
        return await callback_query.answer("❌ Balasan dibatalkan.", show_alert=True)

    # Kirim balasan ke grup pelapor
    text_to_send = (
        f"💬 <b>Balasan dari Admin:</b>\n\n"
        f"{reply['text']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 <b>Admin:</b> {admin.mention}\n"
        f"👤 <b>Untuk Pelapor:</b> <a href='tg://user?id={info['user_id']}'>Pelapor</a>"
    )

    try:
        await client.send_photo(info["chat_id"], photo=LOGO_URL, caption=text_to_send)
        try:
            await client.edit_message_text(admin.id, reply["confirm_msg_id"], "✅ Balasan berhasil dikirim ke grup pelapor.")
        except Exception:
            pass
    except Exception as e:
        try:
            await client.edit_message_text(admin.id, reply["confirm_msg_id"], f"⚠️ Gagal kirim ke grup: {e}")
        except Exception:
            pass
        return await callback_query.answer("⚠️ Gagal mengirim balasan.", show_alert=True)
    finally:
        # bersihkan pending
        if "pending_reply" in info:
            del info["pending_reply"]

    await callback_query.answer("✅ Balasan dikirim ke grup pelapor.", show_alert=True)


# === AUTO CLEAN + RINGKASAN HARIAN (22:00 WIB Surabaya) ===
async def auto_clean_reports(client):
    while True:
        now_server = datetime.now()
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
                try:
                    await reports_col.delete_one({"log_msg_id": msg_id})
                except Exception:
                    pass

        # Ringkasan harian 22:00 WIB (Asia/Jakarta / UTC+7)
        wib = datetime.now(timezone(timedelta(hours=7)))
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
            # pastikan tidak mengirim beberapa kali dalam menit yang sama
            await asyncio.sleep(60)

        await asyncio.sleep(60)


@app.on_message(filters.command("start"))
async def start_auto_task(client, message):
    # jalankan auto-clean & ringkasan
    asyncio.create_task(auto_clean_reports(client))
    await message.reply_text("✅ Auto-clean & laporan harian (22:00 WIB) aktif.")


__MODULE__ = "Admin"
__HELP__ = """
**📣 Fitur Report Admin (Lengkap + MongoDB + Konfirmasi + Ringkasan Harian 22:00 WIB)**

- `/report <masalah>` → kirim laporan ke grup log & notifikasi admin
- Admin bisa balas via bot (DM) → preview → konfirmasi → kirim ke grup pelapor (mention)
- Tandai selesai sinkron MongoDB
- Auto hapus laporan lama (24 jam)
- Ringkasan harian jam 22:00 WIB (Surabaya / Asia/Jakarta)
"""
