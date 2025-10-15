import os
import asyncio
from datetime import datetime, timezone, timedelta
from pyrogram import Client
from ANNIEMUSIC import LOGGER

# Ambil dari ENV Heroku (LOGGER_ID)
LOG_GROUP_ID = int(os.getenv("LOGGER_ID", 0))

# 📸 Header image (bisa diganti kalau mau)
HEADER_IMAGE = (
    "https://raw.githubusercontent.com/mmahsunaz-eng/Onlyforachabot/"
    "623909aba0de9f88ed8756c71ab53ac7af878e35/"
    "ANNIEMUSIC/assets/file_00000000e5e462088641d9a6402214ca.png"
)

# 🕒 Variabel global untuk stopwatch
maintenance_start_time = None
auto_update_task = None  # untuk menyimpan task auto-update


# 🧮 Hitung durasi maintenance
def get_maintenance_duration():
    if not maintenance_start_time:
        return 0, "0 detik"
    duration = datetime.now(timezone(timedelta(hours=7))) - maintenance_start_time
    total_seconds = int(duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    text = f"{hours} jam {minutes} menit {seconds} detik"
    return total_seconds, text


# 🔁 Kirim update durasi tiap 10 menit
async def auto_update_log(client):
    global maintenance_start_time
    if not LOG_GROUP_ID:
        return

    while maintenance_start_time:
        total_seconds, duration_text = get_maintenance_duration()
        caption = (
            "🕓 <b>Update Durasi Maintenance</b>\n\n"
            f"⏱️ <b>Berjalan selama:</b> <code>{duration_text}</code>\n"
            f"🪪 <b>Logger:</b> <code>{LOG_GROUP_ID}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💠 <i>Auto update setiap 10 menit oleh sistem</i>"
        )
        try:
            await client.send_message(LOG_GROUP_ID, caption)
        except Exception as e:
            LOGGER("ANNIEMUSIC").warning(f"Gagal kirim auto-update: {e}")
        await asyncio.sleep(600)  # 10 menit


# ⚙️ Fungsi utama: maintenance_handler (tanpa decorator)
async def maintenance_handler(client: Client, message):
    global maintenance_start_time, auto_update_task

    if len(message.command) < 2:
        return await message.reply_text(
            "Gunakan:\n"
            "`/maintenance enable` — aktifkan mode maintenance\n"
            "`/maintenance disable` — matikan mode maintenance"
        )

    action = message.command[1].lower()
    user = message.from_user
    admin_name = user.first_name if user else "Tidak diketahui"
    admin_id = user.id if user else 0
    admin_repr = f"<a href='tg://user?id={admin_id}'>{admin_name}</a>"
    now_time = datetime.now(timezone(timedelta(hours=7))).strftime("%d %B %Y • %H:%M")

    # 🟢 ENABLE
    if action == "enable":
        if maintenance_start_time:
            return await message.reply_text("⚠️ Maintenance sudah aktif sebelumnya!")

        maintenance_start_time = datetime.now(timezone(timedelta(hours=7)))
        LOGGER("ANNIEMUSIC").info("🟢 Maintenance mode ENABLED — Stopwatch dimulai.")

        caption = (
            "🛠️ <b>ＭＡＩＮＴＥＮＡＮＣＥ ＬＯＧ</b> 🛠️\n\n"
            "<b>Status:</b> 🟢 <code>ENABLED</code>\n"
            f"🕒 <b>Waktu mulai:</b> {now_time}\n"
            f"👤 <b>Diaktifkan oleh:</b> {admin_repr}\n"
            f"🪪 <b>ID Admin:</b> <code>{admin_id}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💠 <b>Diterima oleh:</b> ᴏꜰꜰɪᴄɪᴀʟ 「 Oɴʟʏғᴏʀᴀᴄʜᴀ ✘ ʙᴏᴛ 」"
        )

        try:
            await client.send_photo(LOG_GROUP_ID, photo=HEADER_IMAGE, caption=caption)
        except Exception as e:
            LOGGER("ANNIEMUSIC").warning(f"Gagal kirim log enable: {e}")

        # Jalankan auto update durasi
        auto_update_task = asyncio.create_task(auto_update_log(client))

        return await message.reply_text(
            "🟢 Maintenance diaktifkan.\n🧾 Laporan & auto stopwatch dimulai."
        )

    # 🔴 DISABLE
    elif action == "disable":
        if not maintenance_start_time:
            return await message.reply_text(
                "❌ Stopwatch belum berjalan. Aktifkan dulu maintenance mode."
            )

        total_seconds, duration_text = get_maintenance_duration()

        # 🎨 Tentukan kategori
        if total_seconds < 3600:
            color_icon = "🟢"
            color_text = "Normal"
        elif total_seconds < 10800:
            color_icon = "🟡"
            color_text = "Sedang"
        else:
            color_icon = "🔴"
            color_text = "Lama"

        caption = (
            "🛠️ <b>ＭＡＩＮＴＥＮＡＮＣＥ ＬＯＧ</b> 🛠️\n\n"
            f"<b>Status:</b> 🔴 <code>DISABLED</code>\n"
            f"⏱️ <b>Durasi:</b> <code>{duration_text}</code>\n"
            f"🎯 <b>Kategori:</b> {color_icon} <i>{color_text}</i>\n"
            f"📅 <b>Berakhir pada:</b> {now_time}\n"
            f"👤 <b>Dimatikan oleh:</b> {admin_repr}\n"
            f"🪪 <b>ID Admin:</b> <code>{admin_id}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💠 <b>Diterima oleh:</b> ᴏꜰꜰɪᴄɪᴀʟ 「 Oɴʟʏғᴏʀᴀᴄʜᴀ ✘ ʙᴏᴛ 」"
        )

        # Hentikan stopwatch & auto update
        maintenance_start_time = None
        if auto_update_task:
            auto_update_task.cancel()

        try:
            await client.send_photo(LOG_GROUP_ID, photo=HEADER_IMAGE, caption=caption)
        except Exception as e:
            LOGGER("ANNIEMUSIC").warning(f"Gagal kirim log disable: {e}")

        LOGGER("ANNIEMUSIC").info(
            f"{color_icon} Maintenance mode DISABLED — Durasi {duration_text} ({color_text})"
        )

        return await message.reply_text(
            "🔴 Maintenance dimatikan.\n🧾 Laporan dikirim ke grup log."
        )

    else:
        await message.reply_text("❌ Gunakan hanya `enable` atau `disable`.")
