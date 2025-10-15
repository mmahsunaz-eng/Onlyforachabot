from pyrogram import filters
from pyrogram.types import Message

from ANNIEMUSIC import app
from ANNIEMUSIC.misc import SUDOERS
from ANNIEMUSIC.utils.database import (
    get_lang,
    is_maintenance,
    maintenance_off,
    maintenance_on,
)
from strings import get_string

# 🔹 Import dari file kamu
from ANNIEMUSIC.autotimermaintenance import maintenance_handler


@app.on_message(filters.command(["maintenance", "maint"]) & SUDOERS)
async def maintenance(client, message: Message):
    """
    Gabungan antara sistem bawaan ANNIEMUSIC dan autotimermaintenance.py
    - Sinkron ke database (maintenance_on/off)
    - Aktifkan stopwatch & auto log updater
    """

    try:
        language = await get_lang(message.chat.id)
        _ = get_string(language)
    except:
        _ = get_string("en")

    usage = _["maint_1"]

    if len(message.command) != 2:
        return await message.reply_text(usage)

    state = message.text.split(None, 1)[1].strip().lower()

    # 🧩 Jalankan mekanisme auto stopwatch dari file autotimermaintenance.py
    await maintenance_handler(client, message)

    # 🗄️ Sinkronkan status ke database ANNIEMUSIC
    if state == "enable":
        # Kalau belum maintenance → aktifkan
        if not await is_maintenance():
            await maintenance_on()
            await message.reply_text(_["maint_2"].format(app.mention))
        else:
            await message.reply_text(_["maint_4"])

    elif state == "disable":
        # Kalau sedang maintenance → matikan
        if await is_maintenance():
            await maintenance_off()
            await message.reply_text(_["maint_3"].format(app.mention))
        else:
            await message.reply_text(_["maint_5"])

    else:
        await message.reply_text(usage)
