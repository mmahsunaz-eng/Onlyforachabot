import asyncio

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteHashExpired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import PLAYLIST_IMG_URL, SUPPORT_CHAT, adminlist
from strings import get_string
from ANNIEMUSIC import YouTube, app
from ANNIEMUSIC.misc import SUDOERS
from ANNIEMUSIC.utils.database import (
    get_assistant,
    get_cmode,
    get_lang,
    get_playmode,
    get_playtype,
    is_active_chat,
    is_maintenance,
)
from ANNIEMUSIC.utils.inline import botplaylist_markup

# Cache untuk link undangan per chat
links = {}


def PlayWrapper(command):
    async def wrapper(client, message):
        # Ambil bahasa user
        language = await get_lang(message.chat.id)
        _ = get_string(language)

        # Cegah dari channel-anonymous
        if message.sender_chat:
            upl = InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="ʜᴏᴡ ᴛᴏ ғɪx ?", callback_data="AnonymousAdmin")]]
            )
            return await message.reply_text(_["general_3"], reply_markup=upl)

        # 🔧 Cek apakah maintenance sedang aktif
        check_status = await is_maintenance()
        print(f"[DEBUG] Maintenance status: {check_status}")

        if not check_status:  # ⬅️ Maintenance aktif (dibalik dari default)
            if message.from_user.id not in SUDOERS:
                text = (
                    "🚧⚙️ <b>ＭＡＩＮＴＥＮＡＮＣＥ ＭＯＤＥ</b> ⚙️🚧\n\n"
                    "📢 <b>Bot saat ini sedang dalam mode pemeliharaan.</b>\n"
                    "Selama proses ini berlangsung, fitur pemutaran musik tidak tersedia.\n\n"
                    f"💠 <b>Bot:</b> {app.mention}\n"
                    f"💬 <b>Dukungan:</b> <a href={SUPPORT_CHAT}>Klik di sini</a>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🙏 <i>Terima kasih atas pengertiannya.</i>"
                )
                return await message.reply_text(text, disable_web_page_preview=True)

        # Hapus command user (biar rapi di chat)
        try:
            await message.delete()
        except Exception:
            pass

        # Deteksi apakah reply audio/video/url
        audio_telegram = (
            (message.reply_to_message.audio or message.reply_to_message.voice)
            if message.reply_to_message
            else None
        )
        video_telegram = (
            (message.reply_to_message.video or message.reply_to_message.document)
            if message.reply_to_message
            else None
        )
        url = await YouTube.url(message)

        # Jika tak ada input apa pun
        if audio_telegram is None and video_telegram is None and url is None:
            if len(message.command) < 2:
                if "stream" in message.command:
                    return await message.reply_text(_["str_1"])
                buttons = botplaylist_markup(_)
                return await message.reply_photo(
                    photo=PLAYLIST_IMG_URL,
                    caption=_["play_18"],
                    reply_markup=InlineKeyboardMarkup(buttons),
                )

        # Mode channel
        if message.command[0][0] == "c":
            chat_id = await get_cmode(message.chat.id)
            if chat_id is None:
                return await message.reply_text(_["setting_7"])
            try:
                chat = await app.get_chat(chat_id)
            except Exception:
                return await message.reply_text(_["cplay_4"])
            channel = chat.title
        else:
            chat_id = message.chat.id
            channel = None

        # Mode play dan siapa yang boleh pakai
        playmode = await get_playmode(message.chat.id)
        playty = await get_playtype(message.chat.id)
        if playty != "Everyone":
            if message.from_user.id not in SUDOERS:
                admins = adminlist.get(message.chat.id)
                if not admins:
                    return await message.reply_text(_["admin_13"])
                elif message.from_user.id not in admins:
                    return await message.reply_text(_["play_4"])

        # Cek mode video/audio
        if message.command[0][0] == "v":
            video = True
        else:
            if "-v" in message.text:
                video = True
            else:
                video = True if message.command[0][1] == "v" else None

        # Jika mode forceplay
        if message.command[0][-1] == "e":
            if not await is_active_chat(chat_id):
                return await message.reply_text(_["play_16"])
            fplay = True
        else:
            fplay = None

        # Jika belum aktifkan voice chat, pastikan assistant join
        if not await is_active_chat(chat_id):
            userbot = await get_assistant(chat_id)
            try:
                try:
                    member = await app.get_chat_member(chat_id, userbot.id)
                except ChatAdminRequired:
                    return await message.reply_text(_["call_1"])

                if member.status in (ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED):
                    return await message.reply_text(
                        _["call_2"].format(app.mention, userbot.id, userbot.name, userbot.username),
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton(text="๏ 𝗨ɴʙᴀɴ 𝗔ssɪsᴛᴀɴᴛ ๏", callback_data="unban_assistant")]]
                        ),
                    )
            except UserNotParticipant:
                if chat_id in links:
                    invitelink = links[chat_id]
                else:
                    if message.chat.username:
                        invitelink = message.chat.username
                        try:
                            await userbot.resolve_peer(invitelink)
                        except Exception:
                            pass
                    else:
                        try:
                            invitelink = await app.export_chat_invite_link(chat_id)
                        except ChatAdminRequired:
                            return await message.reply_text(_["call_1"])
                        except Exception as e:
                            return await message.reply_text(_["call_3"].format(app.mention, type(e).__name__))

                if invitelink.startswith("https://t.me/+"):
                    invitelink = invitelink.replace("https://t.me/+", "https://t.me/joinchat/")

                myu = await message.reply_text(_["call_4"].format(app.mention))
                try:
                    await asyncio.sleep(1)
                    await userbot.join_chat(invitelink)
                except InviteHashExpired:
                    if chat_id in links:
                        del links[chat_id]
                    try:
                        invitelink = await app.export_chat_invite_link(chat_id)
                    except ChatAdminRequired:
                        return await message.reply_text(_["call_1"])
                    except Exception as e:
                        return await message.reply_text(_["call_3"].format(app.mention, type(e).__name__))
                    if invitelink.startswith("https://t.me/+"):
                        invitelink = invitelink.replace("https://t.me/+", "https://t.me/joinchat/")
                    links[chat_id] = invitelink
                    await userbot.join_chat(invitelink)
                except InviteRequestSent:
                    try:
                        await app.approve_chat_join_request(chat_id, userbot.id)
                    except Exception as e:
                        return await message.reply_text(_["call_3"].format(app.mention, type(e).__name__))
                    await asyncio.sleep(3)
                    await myu.edit(_["call_5"].format(app.mention))
                except UserAlreadyParticipant:
                    pass
                except Exception as e:
                    return await message.reply_text(_["call_3"].format(app.mention, type(e).__name__))

                links[chat_id] = invitelink

                try:
                    await userbot.resolve_peer(chat_id)
                except Exception:
                    pass

        # Lanjut ke eksekusi command utama
        return await command(client, message, _, chat_id, video, channel, playmode, url, fplay)

    return wrapper
