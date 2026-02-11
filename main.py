import json
import os
import asyncio
from datetime import datetime
from pyrogram import Client, filters, idle
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types import Update
from pytgcalls.exceptions import NoActiveGroupCall
from dotenv import load_dotenv

load_dotenv()

# --- Yapılandırma ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
JSON_FILE = os.getenv("JSON_FILE")
MUSIC_FOLDER = os.getenv("MUSIC_DIR")
MY_BOT = os.getenv("BOT_USERNAME").replace("@", "")  # @ varsa temizle
CHAR_LIMIT = 4096

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


def fetch_lyrics(song):
    # Şarkı ve Söz Bilgisini Hazırla
    lyrics = song.get("lyrics", "Söz bulunamadı 🎶")
    # CHAR_LIMIT değişkeninin tanımlı olduğundan emin ol (örn: 1000)
    limit = globals().get("CHAR_LIMIT", 1000)
    safe_lyrics = lyrics[: limit - 3] + "..." if len(lyrics) > limit else lyrics

    raw_year = song.get("year", 0)
    try:
        year_val = int(raw_year)
        if year_val == 0:
            year_text = "Bilinmiyor"
        elif year_val < 0:
            year_text = f"M.Ö {abs(year_val)}"
        else:
            year_text = f"M.S {year_val}"
    except (ValueError, TypeError):
        year_text = "Bilinmiyor"

    return (
        f"🎶 **Şu an Çalıyor**\n"
        f"🎵 **Şarkı:** `{song['name']}`\n"
        f"📅 **Yıl:** {year_text}\n\n"
        f"📜 **Sözler:**\n{safe_lyrics}"
    )


# --- MERKEZİ ÇALMA YARDIMCISI ---
async def play_engine(chat_id, song, messenger):
    file_path = os.path.join(MUSIC_FOLDER, f"{song['name']}.mp3")

    # Başlangıçta info_text'i boş tanımlayalım ki finally bloğu hata vermesin
    info_text = ""

    if not os.path.exists(file_path):
        log(f"Dosya Bulunamadı: {file_path}")
        return False

    try:
        # Önceki çağrıdan ayrıl
        try:
            await call_py.leave_group_call(chat_id)
        except:
            pass

        # Çalmayı başlat
        await call_py.join_group_call(chat_id, AudioPiped(file_path))
        log(f"Başlatıldı: {song['name']}")

        info_text = fetch_lyrics(song)

        success = True

    except NoActiveGroupCall:
        info_text = "⚠️ **Hata:** Lütfen önce grupta bir sesli sohbet başlatın!"
        log("Hata: Sesli sohbet aktif değil.")
        success = False

    except Exception as e:
        info_text = f"❌ **Sistem Hatası:** {str(e)}"
        log(f"Çalma Motoru Hatası: {e}")
        success = False

    # Mesaj Gönderme Kısmı
    if info_text:
        try:
            if hasattr(messenger, "reply"):
                info = await messenger.reply(info_text)
            else:
                info = await messenger.send_message(chat_id, info_text)
            asyncio.create_task(auto_delete(info, 30))
        except Exception as msg_err:
            log(f"Mesaj gönderme hatası: {msg_err}")

    return success


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
            log(f"Otomatik geçiş: {next_song['name']}")
            # Mesaj objesi yok, asistan objesini (client) messenger olarak gönderiyoruz
            await play_engine(chat_id, next_song, client)
        else:
            log("Liste sona erdi.")
            is_auto_playing[chat_id] = False
            await call_py.leave_group_call(chat_id)


# --- KOMUTLAR ---


@assistant.on_message(
    filters.command(["play", "start", f"play@{MY_BOT}", f"start@{MY_BOT}"])
    & filters.group
)
async def handle_playback(client, message):
    # Komutu temizle (play@botadi -> play)
    cmd = message.command[0].lower().split("@")[0]
    chat_id = message.chat.id
    asyncio.create_task(auto_delete(message))

    playlist = get_playlist()
    if not playlist:
        return

    query = " ".join(message.command[1:]).lower()
    song, index = None, 0

    if query:
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
        if cmd == "start":
            index, song = 0, playlist[0]

    if not song:
        m = await message.reply(f"❌ `{query}` bulunamadı.")
        return asyncio.create_task(auto_delete(m))

    is_auto_playing[chat_id] = cmd == "start"
    current_song_index[chat_id] = index

    # Messenger olarak 'message' objesini gönderiyoruz
    await play_engine(chat_id, song, message)


@assistant.on_message(
    filters.command(
        [
            "stop",
            f"stop@{MY_BOT}",
            "pause",
            f"pause@{MY_BOT}",
            "resume",
            f"resume@{MY_BOT}",
            "next",
            f"next@{MY_BOT}",
            "prev",
            f"prev@{MY_BOT}",
            "list",
            f"list@{MY_BOT}",
            "lyrics",
            f"lyrics@{MY_BOT}",
        ]
    )
    & filters.group
)
async def control_commands(client, message):
    # Komutu temizle (play@botadi -> play)
    cmd = message.command[0].lower().split("@")[0]
    print(cmd)
    chat_id = message.chat.id
    asyncio.create_task(auto_delete(message))
    playlist = get_playlist()

    try:
        if cmd == "stop":
            is_auto_playing[chat_id] = False
            await call_py.leave_group_call(chat_id)
            m = await message.reply("🛑 **Sonlandırıldı.**")
            asyncio.create_task(auto_delete(m))

        elif cmd == "pause":
            await call_py.pause_stream(chat_id)
            m = await message.reply("⏸ **Duraklatıldı.**")
            asyncio.create_task(auto_delete(m))

        elif cmd == "resume":
            await call_py.resume_stream(chat_id)
            m = await message.reply("▶️ **Devam ediyor.**")
            asyncio.create_task(auto_delete(m))

        elif cmd == "next":
            next_idx = current_song_index.get(chat_id, -1) + 1
            if next_idx < len(playlist):
                current_song_index[chat_id] = next_idx
                await play_engine(chat_id, playlist[next_idx], message)
            else:
                m = await message.reply("🏁 **Liste bitti.**")
                asyncio.create_task(auto_delete(m))

        elif cmd == "prev":
            prev_idx = current_song_index.get(chat_id, 0) - 1
            if prev_idx >= 0:
                current_song_index[chat_id] = prev_idx
                await play_engine(chat_id, playlist[prev_idx], message)
            else:
                m = await message.reply("⏪ **Listenin başındasın.**")
                asyncio.create_task(auto_delete(m))

        elif cmd == "list":
            text = "📂 **Müzik Listesi**\n" + "⎯" * 10 + "\n"
            for i, s in enumerate(playlist):
                mark = "▶️" if current_song_index.get(chat_id) == i else "▫️"
                text += f"{mark} `{s['name']}`\n"

            # Telegram karakter sınırı (4096) kontrolü
            limit = globals().get("CHAR_LIMIT", 1000)
            text = (text[: limit - 3] + "...") if len(text) > limit else text

            m = await message.reply(text)
            asyncio.create_task(auto_delete(m, 30))

        # --- YENİ EKLENEN LYRICS KISMI ---
        elif cmd == "lyrics":
            index = current_song_index.get(chat_id)
            if index is not None and index < len(playlist):
                song = playlist[index]
                text = fetch_lyrics(song)
                m = await message.reply(text)
                asyncio.create_task(auto_delete(m, 300))  # 5 dk sonra silinir
            else:
                m = await message.reply("❌ Şu an çalan bir şarkı yok.")
                asyncio.create_task(auto_delete(m))

    except Exception as e:
        log(f"Komut Hatası ({cmd}): {e}")


async def main():
    log("Asistan başlatılıyor...")
    await assistant.start()
    await call_py.start()
    log("Sistem hazır.")
    await idle()


if __name__ == "__main__":
    assistant.run(main())
