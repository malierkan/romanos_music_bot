import json
import os
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from dotenv import load_dotenv

# Yapılandırmayı Yükle
load_dotenv()


# Log fonksiyonunu anlık çıktı (flush) verecek şekilde güncelledik
def log(message):
    time = datetime.now().strftime("%H:%M:%S")
    formatted_msg = f"[{time}] 🤖 {message}"
    print(formatted_msg, flush=True)


# .env'den gelen dosya yolları
JSON_FILE = os.getenv("JSON_FILE")
ID_TRACKER = os.getenv("ID_FILE")
MUSIC_BOT_CMD = "/play"
BOT_USERNAME = os.getenv("BOT_USERNAME")

# Botu başlatırken terminale ilk bilgileri basıyoruz
log("--- SİSTEM BAŞLATILIYOR ---")
log(f"Yapılandırma: JSON={JSON_FILE} | ID_FILE={ID_TRACKER}")

app = Client(
    "romanos_manager", api_id=os.getenv("API_ID"), api_hash=os.getenv("API_HASH")
)

# --- VERİ YÖNETİMİ ---


def load_playlist():
    if not os.path.exists(JSON_FILE):
        log(f"❌ KRİTİK HATA: {JSON_FILE} bulunamadı!")
        return []
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            log(f"📂 JSON okundu: {len(data)} şarkı mevcut.")
            return data
    except Exception as e:
        log(f"❌ JSON hatası: {e}")
        return []


def get_current_id():
    try:
        if os.path.exists(ID_TRACKER):
            with open(ID_TRACKER, "r") as f:
                val = f.read().strip()
                return int(val) if val else 1
    except:
        pass
    return 1


def save_current_id(new_id):
    try:
        with open(ID_TRACKER, "w") as f:
            f.write(str(new_id))
        log(f"💾 ID kaydedildi: {new_id}")
    except Exception as e:
        log(f"💾 Yazma hatası: {e}")


# --- ANA MANTIK ---


async def play_logic(client, message, song_id):
    log(f"İşlem: ID {song_id} için süreç başladı.")
    playlist = load_playlist()
    song = next(
        (
            item
            for item in playlist
            if isinstance(item, dict) and item.get("id") == song_id
        ),
        None,
    )

    if not song:
        log("Bitti: Liste sonuna ulaşıldı.")
        return

    try:
        # 1. MP3 Gönderimi (Sessiz)
        log(f"Dosya: '{song.get('name')}' gönderiliyor...")
        sent_audio = await client.send_audio(
            chat_id=message.chat.id, audio=song.get("fileid"), disable_notification=True
        )

        # 2. Müzik Botu Tetikleme
        log("Tetikleyici: /play komutu iletildi.")
        trigger_msg = await sent_audio.reply(MUSIC_BOT_CMD)

        # 3. ŞARKIKARTINI GÖNDERME (Hatanın düzeltildiği yer)
        y = song.get("year", 0)
        yil_str = f"M.Ö. {abs(y)}" if y < 0 else str(y)
        info_text = f"""🎶 Şu Anda Çalan 🎶

🎤 **Müziğin İsmi: ** {song.get('name')}

📅 **Dönemi: ** {yil_str}

📜 **Sözleri: ** {song.get('lyrics', '')}"""

        # Burada 'client' değişkeninin 'app' (yani senin Client instance'ın) olduğundan emin oluyoruz
        await client.send_message(chat_id=message.chat.id, text=info_text)
        log("İleti: Bilgi kartı başarıyla gönderildi.")

        # 4. İzleri Sil
        log("Temizlik: İzler 5 saniye içinde silinecek.")
        await asyncio.sleep(5)
        await client.delete_messages(message.chat.id, [sent_audio.id, trigger_msg.id])
        log("Sonuç: Tertemiz bir chat bırakıldı.")

        save_current_id(song_id + 1)

    except Exception as e:
        # Hata buraya düşerse terminalde detaylıca göreceksin
        log(f"Kritik Oynatma Hatası: {e}")


# --- KOMUTLAR ---


@app.on_message(filters.command(["baslat", f"baslat@{BOT_USERNAME}"]) & filters.group)
async def start_cmd(client, message):
    log("📥 Komut: /baslat")
    await message.delete()
    save_current_id(1)
    await play_logic(client, message, 1)


# --- YENİ KOMUTLAR: ÖNCEKİ, SONRAKİ, DURDUR, DURAKLAT ---


@app.on_message(filters.command(["onceki", f"onceki@{BOT_USERNAME}"]) & filters.group)
async def prev_cmd(client, message):
    log("Komut: /onceki")
    await message.delete()
    current_id = get_current_id()
    new_id = max(
        1, current_id - 2
    )  # Bir öncekine gitmek için 2 geri (çünkü play_logic 1 ileri atıyor)
    save_current_id(new_id)
    await play_logic(client, message, new_id)


@app.on_message(filters.command(["sonraki", f"sonraki@{BOT_USERNAME}"]) & filters.group)
async def next_cmd(client, message):
    log("Komut: /sonraki")

    # Kullanıcının yazdığı komutu siliyoruz
    await message.delete()

    # Mevcut ID'yi alıyoruz (play_logic zaten sonunda +1 ekleyip kaydedecek)
    current_id = get_current_id()

    log(f"Sıradaki şarkı tetikleniyor: ID {current_id}")
    await play_logic(client, message, current_id)


@app.on_message(
    filters.command(
        [
            "duraklat",
            f"duraklat@{BOT_USERNAME}",
            "durdur",
            f"durdur@{BOT_USERNAME}",
            "devam",
            f"devam@{BOT_USERNAME}",
        ]
    )
    & filters.group
)
async def control_cmds(client, message):
    # Kullanıcının yazdığı komutu al (/duraklat -> /duraklat)
    cmd = str(message.text.split()[0])
    cmd = cmd.replace(f"@{BOT_USERNAME}", "")

    log(f"Kontrol: {cmd} komutu iletiliyor.")

    await message.delete()  # Kullanıcı komutunu sil

    # Müzik botuna komutu gönder
    ctrl_msg = await client.send_message(chat_id=message.chat.id, text=cmd)

    # 3 saniye sonra botun yazdığı komutu da sil (Chat tertemiz kalsın)
    await asyncio.sleep(3)
    await ctrl_msg.delete()


# --- PLAY LOGIC VE DİĞERLERİ AYNI KALIYOR ---


# @app.on_message(filters.command("scan") & filters.group)
# async def channel_scanner(client, message):
#     # Komut kullanımı: /scan @kanaladi veya kanal_id
#     if len(message.command) < 2:
#         await message.reply("Lütfen kanal kullanıcı adını yaz: `/scan @kanal_linki`")
#         return

#     target_chat = message.command[1]
#     log(f"Tarama başlatılıyor: {target_chat}")

#     found_songs = []
#     count = 1

#     async for msg in client.get_chat_history(target_chat):
#         if msg.audio:
#             song_data = {
#                 "id": count,
#                 "name": msg.audio.file_name or "Bilinmeyen Şarkı",
#                 "fileid": msg.audio.file_id,
#                 "year": 0,  # Bunu manuel düzenlersin
#                 "lyrics": "🎶",
#             }
#             found_songs.append(song_data)
#             count += 1

#     # Sonuçları JSON dosyasına kaydet
#     with open("fetched_musics.json", "w", encoding="utf-8") as f:
#         json.dump(found_songs, f, ensure_ascii=False, indent=4)

#     log(f"Tarama bitti: {len(found_songs)} şarkı kaydedildi.")
#     await message.reply(
#         f"✅ Tarama tamamlandı! `{len(found_songs)}` şarkı `fetched_musics.json` dosyasına yazıldı."
#     )


# Bot bağlandığında terminalde görelim
@app.on_message(filters.private)
async def private_log(client, message):
    log(f"📩 Özel mesaj alındı (Kullanıcı: {message.from_user.id})")


log("🚀 Bot pyrogram üzerinden bağlanıyor...")
app.run()
