from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_URL = os.getenv("MONGO_URL")
if not MONGO_URL:
    raise ValueError("❌ MONGO_URL belum diatur di environment variables!")

mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["ANNIEMUSIC"]
reports_col = db["reports"]

async def setup_ttl_index():
    try:
        indexes = await reports_col.index_information()
        if "created_at_1" not in indexes:
            await reports_col.create_index("created_at", expireAfterSeconds=86400)
            print("[MongoDB] ✅ TTL index dibuat (hapus laporan setelah 24 jam)")
    except Exception as e:
        print(f"[MongoDB] ⚠️ Gagal membuat TTL index: {e}")
