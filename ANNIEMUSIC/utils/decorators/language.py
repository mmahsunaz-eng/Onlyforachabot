from ANNIEMUSIC import app
from config import SUPPORT_CHAT
from ANNIEMUSIC.misc import SUDOERS
from ANNIEMUSIC.utils.database import get_lang, is_maintenance
from strings import get_string


def language(mystic):
    async def wrapper(_, message, **kwargs):
        # 🔧 Perbaikan logika & desain pesan maintenance
        if await is_maintenance() is True:
            if message.from_user.id not in SUDOERS:
                return await message.reply_text(
                    text=(
                        "🚨 <b>ＰＥＲＨＡＴＩＡＮ</b> 🚨\n\n"
                        "Bot sedang dalam mode <b>pemeliharaan</b>.\n"
                        "Selama proses ini berlangsung, semua perintah dinonaktifkan.\n\n"
                        f"💠 <b>Bot:</b> {app.mention}\n"
                        f"💬 <b>Dukungan:</b> <a href={SUPPORT_CHAT}>Klik di sini</a>\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        "🙏 Terima kasih atas pengertiannya."
                    ),
                    disable_web_page_preview=True,
                )

        try:
            await message.delete()
        except:
            pass

        try:
            language = await get_lang(message.chat.id)
            language = get_string(language)
        except:
            language = get_string("en")
        return await mystic(_, message, language)

    return wrapper


def languageCB(mystic):
    async def wrapper(_, CallbackQuery, **kwargs):
        if await is_maintenance() is True:
            if CallbackQuery.from_user.id not in SUDOERS:
                return await CallbackQuery.answer(
                    f"{app.mention} sedang dalam mode pemeliharaan. "
                    "Coba lagi nanti setelah bot kembali normal.",
                    show_alert=True,
                )
        try:
            language = await get_lang(CallbackQuery.message.chat.id)
            language = get_string(language)
        except:
            language = get_string("en")
        return await mystic(_, CallbackQuery, language)

    return wrapper


def LanguageStart(mystic):
    async def wrapper(_, message, **kwargs):
        try:
            language = await get_lang(message.chat.id)
            language = get_string(language)
        except:
            language = get_string("en")
        return await mystic(_, message, language)

    return wrapper
