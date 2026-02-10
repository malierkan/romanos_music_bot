import json
import os
import asyncio
from datetime import datetime
from pyrogram import Client, filters, idle
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types import Update
from dotenv import load_dotenv

load_dotenv()

# Yapılandırma
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
JSON_FILE = os.getenv("JSON_FILE")
MUSIC_FOLDER = os.getenv("MUSIC_DIR")
MY_BOT = os.getenv("BOT_USERNAME")

# Global Durum Takibi
is_auto_playing = {}  # {chat_id: True/False}
current_song_index = {}  # {chat_id: index}

assistant = Client("asistant_account", API_ID, API_HASH, session_string=SESSION_STRING)
call_py = PyTgCalls(assistant)


def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🎵 {message}", flush=True)


async def auto_delete(message, delay=5):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass


def get_playlist():
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"JSON Okuma Hatası: {e}")
        return []


# --- MERKEZİ ÇALMA YARDIMCISI ---
async def play_engine(chat_id, song):
    """Dosyayı bulur ve çalmayı başlatır."""
    file_path = os.path.join(MUSIC_FOLDER, f"{song['name']}.mp3")

    if not os.path.exists(file_path):
        log(f"Dosya Bulunamadı: {file_path}")
        return False

    try:
        # Önceki aramadan kalmışsa temizle
        try:
            await call_py.leave_group_call(chat_id)
        except:
            pass

        await call_py.join_group_call(chat_id, AudioPiped(file_path))
        log(f"Başlatıldı: {song['name']}")
        return True
    except Exception as e:
        log(f"Çalma Motoru Hatası: {e}")
        return False


# --- OTOMATİK GEÇİŞ SİSTEMİ ---
@call_py.on_stream_end()
async def on_stream_end(client, update: Update):
    chat_id = update.chat_id
    if is_auto_playing.get(chat_id):
        playlist = get_playlist()
        next_idx = current_song_index.get(chat_id, 0) + 1

        if next_idx < len(playlist):
            current_song_index[chat_id] = next_idx
            next_song = playlist[next_idx]
            log(f"Sıradaki şarkıya geçiliyor: {next_song['name']}")
            await play_engine(chat_id, next_song)
        else:
            log("Liste sona erdi.")
            is_auto_playing[chat_id] = False
            await call_py.leave_group_call(chat_id)


# --- KOMUTLAR ---


@assistant.on_message(
    filters.command(["play", f"play@{MY_BOT}", "start", f"start@{MY_BOT}"]) & filters.group
)
async def handle_playback(client, message):
    cmd = message.command[0]
    chat_id = message.chat.id
    asyncio.create_task(auto_delete(message))

    playlist = get_playlist()
    if not playlist:
        return

    # Arama sorgusunu birleştir
    query = " ".join(message.command[1:]).lower()

    # Şarkı Bulma Mantığı
    song = None
    index = 0

    if query:
        # Önce tam isim eşleşmesi, sonra kısmi isim eşleşmesi
        song_data = next(
            ((i, s) for i, s in enumerate(playlist) if query == s["name"].lower()),
            next(
                ((i, s) for i, s in enumerate(playlist) if query in s["name"].lower()),
                None,
            ),
        )
        if song_data:
            index, song = song_data
    else:
        # Sorgu yoksa ve /start ise listenin başı
        if cmd == "start" or f"start@{MY_BOT}":
            index, song = 0, playlist[0]

    if not song:
        m = await message.reply(f"❌ `{query}` isminde bir şarkı bulunamadı.")
        return asyncio.create_task(auto_delete(m))

    # Modu Kaydet
    is_auto_playing[chat_id] = cmd == "start" or f"start@{MY_BOT}"
    current_song_index[chat_id] = index

    # Çalma İşlemi
    if await play_engine(chat_id, song):
        status = "🔄 Otomatik Liste" if cmd == "start" or f"start@{MY_BOT}" else "🎯 Tekli Çalma"
        info = await message.reply(
            f"""
🎶 **{status} Başladı**
🎵 **Şarkı:** `{song['name']}`

📅 **Yıl:** {song.get('year', 'Bilinmiyor')}

📜 **Sözler:**\n{song.get('lyrics', '🎶')}"""
        )
        asyncio.create_task(auto_delete(info, 30))


@assistant.on_message(filters.command(["stop", f"stop@{MY_BOT}"]) & filters.group)
async def stop_music(client, message):
    is_auto_playing[message.chat.id] = False
    try:
        await call_py.leave_group_call(message.chat.id)
    except:
        pass
    log("Kullanıcı tarafından durduruldu.")
    asyncio.create_task(auto_delete(message))


@assistant.on_message(filters.command(["pause", f"pause@{MY_BOT}"]) & filters.group)
async def pause_music(client, message):
    try:
        await call_py.pause_stream(message.chat.id)
        log(f"Duraklatıldı: {message.chat.id}")
        m = await message.reply("⏸ **Yayın duraklatıldı.**")
        asyncio.create_task(auto_delete(message))
        asyncio.create_task(auto_delete(m))
    except Exception as e:
        log(f"Pause Hatası: {e}")


@assistant.on_message(filters.command(["resume", f"resume@{MY_BOT}"]) & filters.group)
async def resume_music(client, message):
    try:
        await call_py.resume_stream(message.chat.id)
        log(f"Devam ettiriliyor: {message.chat.id}")
        m = await message.reply("▶️ **Yayın devam ediyor.**")
        asyncio.create_task(auto_delete(message))
        asyncio.create_task(auto_delete(m))
    except Exception as e:
        log(f"Resume Hatası: {e}")


@assistant.on_message(filters.command(["next", f"next@{MY_BOT}"]) & filters.group)
async def next_song(client, message):
    chat_id = message.chat.id
    playlist = get_playlist()
    asyncio.create_task(auto_delete(message))

    # Mevcut indeksi al ve 1 artır
    current_idx = current_song_index.get(chat_id, -1)
    next_idx = current_idx + 1

    if next_idx < len(playlist):
        current_song_index[chat_id] = next_idx
        song = playlist[next_idx]
        await play_engine(chat_id, song)

        info = await message.reply(f"⏭ **Sonraki şarkıya geçildi:**\n`{song['name']}`")
        asyncio.create_task(auto_delete(info, 10))
    else:
        m = await message.reply("🏁 **Listenin sonuna geldik.**")
        asyncio.create_task(auto_delete(m))


@assistant.on_message(filters.command(["prev", f"prev@{MY_BOT}"]) & filters.group)
async def prev_song(client, message):
    chat_id = message.chat.id
    playlist = get_playlist()
    asyncio.create_task(auto_delete(message))

    # Mevcut indeksi al ve 1 azalt
    current_idx = current_song_index.get(chat_id, 0)
    prev_idx = current_idx - 1

    if prev_idx >= 0:
        current_song_index[chat_id] = prev_idx
        song = playlist[prev_idx]
        await play_engine(chat_id, song)

        info = await message.reply(f"⏮ **Önceki şarkıya dönüldü:**\n`{song['name']}`")
        asyncio.create_task(auto_delete(info, 10))
    else:
        m = await message.reply("⏪ **Zaten listenin başındasın.**")
        asyncio.create_task(auto_delete(m))


@assistant.on_message(filters.command(["list", f"list@{MY_BOT}"]) & filters.group)
async def list_songs(client, message):
    # Komut mesajını 5 saniye sonra sil
    asyncio.create_task(auto_delete(message))

    playlist = get_playlist()
    chat_id = message.chat.id

    if not playlist:
        return await message.reply(
            "❌ Oynatma listesi boş veya JSON dosyası bulunamadı."
        )

    # Liste mesajını oluştur
    text = "📂 **Güncel Müzik Listesi**\n"
    text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"

    # Sadece ilk %limit% şarkıyı göster (Telegram mesaj limitine takılmamak için)
    limit = 200
    for i, s in enumerate(playlist[:limit]):
        # Eğer o an bu şarkı çalıyorsa yanına işaret koy
        mark = "▶️" if current_song_index.get(chat_id) == i else "▫️"
        text += f"{mark} `{s['name']}`\n"

    if len(playlist) > limit:
        text += f"\n... ve {len(playlist)-limit} şarkı daha mevcut."

    text += "\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    text += "💡 _Şarkı başlatmak için:_ `/play isim`"

    # Listeyi gönder ve 30 saniye sonra silinmesi için göreve ekle
    reply = await message.reply(text)
    asyncio.create_task(auto_delete(reply, 30))


async def main():
    log("Asistan başlatılıyor...")
    await assistant.start()
    await call_py.start()
    log("Sistem hazır, komut bekleniyor.")
    await idle()


if __name__ == "__main__":
    assistant.run(main())
