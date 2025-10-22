import asyncio
import requests
from pathlib import Path
from urllib.parse import urlsplit

from config import COOKIE_URL
from ANNIEMUSIC.utils.errors import capture_internal_err

# Lokasi penyimpanan cookie
COOKIE_PATH = Path("ANNIEMUSIC/assets/cookies.txt")

# Gunakan User-Agent browser asli (hindari blokir 403)
YT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.1 Safari/537.36"
)


def _extract_paste_id(url: str) -> str:
    """Ambil ID dari URL pastebin/batbin"""
    path = urlsplit(url).path.rstrip("/")
    parts = [p for p in path.split("/") if p]
    return parts[-1] if parts else ""


def resolve_raw_cookie_url(url: str) -> str:
    """Ubah URL normal jadi URL raw (untuk pastebin/batbin)"""
    url = (url or "").strip()
    low = url.lower()

    if "pastebin.com/" in low and "/raw/" not in low:
        paste_id = _extract_paste_id(url)
        return f"https://pastebin.com/raw/{paste_id}" if paste_id else url

    if "batbin.me/" in low and "/raw/" not in low:
        paste_id = _extract_paste_id(url)
        return f"https://batbin.me/raw/{paste_id}" if paste_id else url

    return url


@capture_internal_err
async def fetch_and_store_cookies():
    """
    Mengambil cookies.txt dari URL dan menyimpannya ke assets.
    Sekaligus memastikan format benar dan tidak kosong.
    """
    if not COOKIE_URL:
        raise EnvironmentError("⚠️ ᴄᴏᴏᴋɪᴇ_ᴜʀʟ ɴᴏᴛ sᴇᴛ ɪɴ ᴇɴᴠ.")

    raw_url = resolve_raw_cookie_url(COOKIE_URL)
    print(f"[COOKIE FETCH] Fetching from: {raw_url}")

    try:
        # Gunakan User-Agent Chrome agar tidak diblokir
        response = await asyncio.to_thread(
            requests.get,
            raw_url,
            timeout=20,
            headers={"User-Agent": YT_USER_AGENT},
        )
        response.raise_for_status()
    except Exception as e:
        raise ConnectionError(f"⚠️ ɴɪᴇ ᴄᴀɴ'ᴛ ꜰᴇᴛᴄʜ ᴄᴏᴏᴋɪᴇs:\n{e}")

    cookies = (response.text or "").strip()

    # Validasi isi cookies
    if not cookies.startswith("# Netscape"):
        raise ValueError("⚠️ ɪɴᴠᴀʟɪᴅ ᴄᴏᴏᴋɪᴇ ꜰᴏʀᴍᴀᴛ. ɴᴇᴇᴅs ɴᴇᴛsᴄᴀᴘᴇ ꜰᴏʀᴍᴀᴛ.")

    if len(cookies) < 100:
        raise ValueError("⚠️ ᴄᴏᴏᴋɪᴇ ᴄᴏɴᴛᴇɴᴛ ᴛᴏᴏ sʜᴏʀᴛ. ᴘᴏssɪʙʟʏ ɪɴᴠᴀʟɪᴅ.")

    COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        COOKIE_PATH.write_text(cookies, encoding="utf-8")
        print(f"[COOKIE FETCH] ✅ Cookies saved to: {COOKIE_PATH}")
    except Exception as e:
        raise IOError(f"⚠️ ғᴀɪʟᴇᴅ ᴛᴏ sᴀᴠᴇ ᴄᴏᴏᴋɪᴇs: {e}")
