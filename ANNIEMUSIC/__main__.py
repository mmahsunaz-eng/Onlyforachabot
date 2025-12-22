import os
import asyncio
import importlib
from datetime import datetime

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from ANNIEMUSIC import LOGGER, app, userbot
from ANNIEMUSIC.core.call import StreamController
from ANNIEMUSIC.misc import sudo
from ANNIEMUSIC.plugins import ALL_MODULES
from ANNIEMUSIC.utils.database import get_banned_users, get_gbanned
from ANNIEMUSIC.utils.cookie_handler import fetch_and_store_cookies

JARVIS = StreamController

# 🧩 MongoDB Setup
from motor.motor_asyncio import AsyncIOMotorClient
from ANNIEMUSIC.plugins.admins.report import auto_clean_reports


# === MONGODB CONNECTION ===
MONGO_URL = os.getenv("MONGO_DB_URI", None)
mongo_client = None
db = None
reports_col = None

if not MONGO_URL:
    LOGGER("MongoDB").warning("⚠️ Environment variable MONGO_DB_URI tidak ditemukan.")
else:
    try:
        mongo_client = AsyncIOMotorClient(MONGO_URL)
        db = mongo_client["Annie"]  # ✅ database utama Annie
        reports_col = db["reports"]
        LOGGER("MongoDB").info("✅ Terhubung ke MongoDB database 'Annie'")
    except Exception as e:
        LOGGER("MongoDB").error(f"❌ Gagal koneksi ke MongoDB: {e}")


async def setup_ttl_index():
    """Buat TTL Index agar laporan otomatis terhapus setelah 24 jam."""
    if reports_col is None:
        LOGGER("MongoDB").warning("⚠️ Tidak terkoneksi ke collection 'reports' — TTL Index dilewati.")
        return "⚠️ Tidak terkoneksi"
    try:
        indexes = await reports_col.index_information()
        if "created_at_1" not in indexes:
            await reports_col.create_index("created_at", expireAfterSeconds=86400)
            LOGGER("MongoDB").info("✅ TTL Index dibuat untuk 'created_at' (24 jam).")
            return "✅ TTL Index dibuat"
        else:
            LOGGER("MongoDB").info("✅ TTL Index sudah ada (24 jam).")
            return "✅ TTL Index sudah ada"
    except Exception as e:
        LOGGER("MongoDB").error(f"⚠️ Gagal membuat TTL Index: {e}")
        return "⚠️ Gagal membuat TTL Index"


# === INISIALISASI BOT ===
async def init():
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LOGGER("ANNIEMUSIC").info("🚀 Starting Annie Music Bot...")
    LOGGER("ANNIEMUSIC").info(f"🕓 Startup Time: {start_time}")

    # 🔐 Validasi Pyrogram Session
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error(
            "❌ Assistant session belum diatur! Harap isi minimal satu STRING di config."
        )
        exit()

    # 🍪 Load YouTube cookies
    try:
        await fetch_and_store_cookies()
        LOGGER("ANNIEMUSIC").info("🍪 YouTube cookies loaded successfully ✅")
    except Exception as e:
        LOGGER("ANNIEMUSIC").warning(f"⚠️ Cookie error: {e}")

    # 👑 Load sudo users
    await sudo()
    LOGGER("ANNIEMUSIC").info("👑 Sudo users loaded successfully.")

    # 🚫 Load banned & gbanned users
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
        LOGGER("ANNIEMUSIC").info(f"🚫 Loaded {len(BANNED_USERS)} banned users.")
    except Exception as e:
        LOGGER("ANNIEMUSIC").warning(f"⚠️ Gagal memuat banned users: {e}")

    # 🧠 Setup MongoDB TTL Index
    ttl_status = await setup_ttl_index()

    # 🚀 Start bot utama
    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("ANNIEMUSIC.plugins" + all_module)
    LOGGER("ANNIEMUSIC.plugins").info("🎶 Annie's modules loaded successfully.")

    # 🧠 Jalankan userbot & JARVIS (voice call)
    await userbot.start()
    await JARVIS.start()

    # 🎧 Test koneksi voice chat
    try:
        await JARVIS.stream_call(
            "http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4"
        )
    except NoActiveGroupCall:
        LOGGER("ANNIEMUSIC").error(
            "⚠️ Voice chat tidak aktif di log group/channel Anda.\n\nAnnie Bot dihentikan..."
        )
        exit()
    except Exception:
        pass

    await JARVIS.decorators()
    LOGGER("ANNIEMUSIC").info("🎶 Annie Music Robot Started Successfully...")

    # 🧹 Jalankan auto-clean laporan
    asyncio.create_task(auto_clean_reports(app))
    LOGGER("ANNIEMUSIC").info("🧹 Auto-clean report aktif • Berjalan setiap 1 menit ✅🚀")

    # 📊 Ringkasan status startup
    LOGGER("ANNIEMUSIC").info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    LOGGER("ANNIEMUSIC").info("🎧 Annie Music System Status:")
    LOGGER("ANNIEMUSIC").info(f"├─ MongoDB: {'✅ Connected' if db is not None else '⚠️ Not Connected'}")
    LOGGER("ANNIEMUSIC").info(f"├─ TTL Index: {ttl_status}")
    LOGGER("ANNIEMUSIC").info("├─ Auto-clean report: ✅ Active")
    LOGGER("ANNIEMUSIC").info(f"├─ Startup Time: {start_time}")
    LOGGER("ANNIEMUSIC").info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 💤 Tetap hidup
    LOGGER("ANNIEMUSIC").info(
        "\x41\x6e\x6e\x69\x65\x20\x4d\x75\x73\x69\x63\x20\x52\x6f\x62\x6f\x74\x20\x53\x74\x61\x72\x74\x65\x64\x20\x53\x75\x63\x63\x65\x73\x73\x66\x75\x6c\x6c\x79\x2e\x2e\x2e"
    )
    await idle()

    # 🔻 Saat bot berhenti
    await app.stop()
    await userbot.stop()
    LOGGER("ANNIEMUSIC").info("sᴛᴏᴘᴘɪɴɢ ᴀɴɴɪᴇ ᴍᴜsɪᴄ ʙᴏᴛ ...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
