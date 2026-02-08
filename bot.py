import os
import json
import asyncio
from dotenv import load_dotenv
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pytgcalls.types import Update

# .env dosyasındaki verileri yükle
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
GROUP_LINK = os.getenv("GROUP_LINK").replace("https://t.me/", "").replace("t.me/", "")
MUSIC_FOLDER = os.getenv("MUSIC_FOLDER")
JSON_FILE = os.getenv("JSON_FILE")

# Pyrogram ve PyTgCalls kurulumu
app = Client("music_bot_session", API_ID, API_HASH)
call_py = PyTgCalls(app)

# Durum takibi için global değişkenler
resolved_chat_id = None
current_index = 0
last_message_id = None


def load_playlist():
    """JSON dosyasından çalma listesini yükler."""
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


async def resolve_chat():
    """Grup linkinden ID'yi çözer."""
    global resolved_chat_id
    try:
        chat = await app.get_chat(GROUP_LINK)
        resolved_chat_id = chat.id
        print(f"✅ Hedef Grup: {chat.title} (ID: {resolved_chat_id})")
    except Exception as e:
        print(f"❌ Grup ID'si alınamadı: {e}")
        exit()


async def play_next_track():
    """Sıradaki şarkıyı oynatır ve bilgileri gruba iletir."""
    global current_index, last_message_id

    playlist = load_playlist()

    if current_index >= len(playlist):
        print("🔄 Liste bitti, başa dönülüyor...")
        current_index = 0

    track = playlist[current_index]
    file_path = os.path.join(MUSIC_FOLDER, track["name"])

    # Dosya kontrolü
    if not os.path.exists(file_path):
        print(f"⚠️ Dosya bulunamadı, atlanıyor: {track['name']}")
        current_index += 1
        await play_next_track()
        return

    # 1. Önceki mesajı sil (Kirlilik yapmasın)
    if last_message_id:
        try:
            await app.delete_messages(resolved_chat_id, last_message_id)
        except:
            pass

    # 2. Yeni mesajı gönder
    text = (
        f"🎶 **Şu an çalıyor:** `{track['name']}`\n"
        f"📅 **Yıl:** {track['year']}\n"
        f"📝 **Açıklama:** {track['description'] if track['description'] else 'Yok'}"
    )
    msg = await app.send_message(resolved_chat_id, text)
    last_message_id = msg.id

    # 3. Ses akışını başlat (v2.x MediaStream kullanır)
    await call_py.play(resolved_chat_id, MediaStream(file_path))
    print(f"🎵 Oynatılıyor: {track['name']}")


@call_py.on_stream_end()
async def stream_end_handler(client, update: Update):
    """Şarkı bittiğinde tetiklenir."""
    global current_index
    print("✨ Şarkı sona erdi, sıradakine geçiliyor...")
    current_index += 1
    await play_next_track()


async def main():
    await app.start()
    await resolve_chat()
    await call_py.start()

    print("🚀 Bot aktif! Müzik başlatılıyor...")
    await play_next_track()

    # Botu açık tut
    await asyncio.idle()
    await app.stop()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
