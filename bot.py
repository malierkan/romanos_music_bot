import os, json, asyncio, sys
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pyrogram.enums import ChatMemberStatus
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types import Update
from pytgcalls.exceptions import NoActiveGroupCall


load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Client("musicbot-bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("musicbot-user", api_id=API_ID, api_hash=API_HASH)

calls = PyTgCalls(user)


PLAYLIST_FILE = "playlist.json"
MUSIC_FOLDER = "music"
PREFIX = "m"
DELAY = 2

current_index = 0
current_message_id = None


# helper functions


def load_playlist():
    print("[i] Opening playlist...")
    with open(PLAYLIST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return sorted(data, key=lambda x: x["id"])


async def is_admin(client, message):
    print("[i] Checking for priviliges...")
    if not message.from_user:
        return False

    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    print(member)

    if member.status == ChatMemberStatus.OWNER:
        return True

    if member.status == ChatMemberStatus.ADMINISTRATOR:
        if member.privileges:
            return member.privileges.can_manage_video_chats
        print("[i] Member is approved.")
        return True

    await message.reply(
        "❌ Bu komutu kullanmak için sesli sohbet yönetme yetkisine sahip olmalısın."
    )

    print("[i] Member is not approved.")
    return False


async def send_info(client, chat_id, track):
    global current_message_id

    name = track["isim"].replace(".mp3", "")
    text = f"🎵 **{name}** ({track['yil']})\n\n{track['aciklama']}"

    if current_message_id:
        try:
            print("[i] Deleting old messages...")
            await client.delete_messages(chat_id, current_message_id)
        except:
            pass

    print("[i] Sending info...")
    msg = await client.send_message(chat_id, text)
    current_message_id = msg.id


async def play_track(chat_id, index):
    try:
        playlist = load_playlist()
        if not playlist:
            print("[i] Playlist is empty.")
            await bot.send_message(chat_id, "❌ Playlist boş.")
            return

        track = playlist[index]
        path = os.path.join(MUSIC_FOLDER, track["isim"])
        print("[i] Playlist is loaded.")

        if not os.path.exists(path):
            print("[i] Music file doesn't exist.")
            await bot.send_message(chat_id, f"❌ Dosya yok: {path}")
            return

        try:
            print("[i] Leaving call...")
            await calls.leave_group_call(chat_id)

        except:
            pass

        finally:
            print("[i] Call is left.")

        try:
            print("[i] Entering call...")
            print(f"[i] Playing: {path}")

            await calls.join_group_call(
                chat_id, AudioPiped(path), stream_type=StreamType().pulse_stream
            )
            await asyncio.sleep(DELAY)

            print("[i] Call is active.")

        except NoActiveGroupCall:
            print("[!] There is not any active call!")
            await bot.send_message(
                chat_id, "🎧 Grupta aktif sesli sohbet yok.\nÖnce sesli sohbeti başlat."
            )
            return

        except Exception as e:
            print("[!] Error:", repr(e))

        await send_info(bot, chat_id, track)

    except Exception as e:
        print("[!] An Error occured!")
        print(repr(e))
        # await bot.send_message(chat_id, str(e))


# listener functions


@bot.on_message(filters.command(PREFIX + "baslat"))
async def start_music(client, message):
    global current_index
    if not await is_admin(client, message):
        return

    me = await client.get_chat_member(message.chat.id, (await client.get_me()).id)

    if me.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        await message.reply("❌ Bot admin değil.")
        return

    await play_track(message.chat.id, current_index)


@bot.on_message(filters.command(PREFIX + "sonraki"))
async def next_music(client, message):
    global current_index
    if not await is_admin(client, message):
        return

    playlist = load_playlist()
    current_index = (current_index + 1) % len(playlist)

    await calls.leave_group_call(message.chat.id)
    await play_track(message.chat.id, current_index)


@bot.on_message(filters.command(PREFIX + "onceki"))
async def prev_music(client, message):
    global current_index
    if not await is_admin(client, message):
        return

    playlist = load_playlist()
    current_index = (current_index - 1) % len(playlist)

    await calls.leave_group_call(message.chat.id)
    await play_track(message.chat.id, current_index)


@bot.on_message(filters.command(PREFIX + "dur"))
async def stop_music(client, message):
    if not await is_admin(client, message):
        return

    await calls.leave_group_call(message.chat.id)


@bot.on_message(filters.command(PREFIX + "sozler"))
async def lyrics(client, message):
    playlist = load_playlist()
    track = playlist[current_index]
    await send_info(client, message.chat.id, track)


@bot.on_message(filters.command(PREFIX + "duraklat"))
async def pause_music(client, message):
    if not await is_admin(client, message):
        return

    await calls.pause_stream(message.chat.id)


@bot.on_message(filters.command(PREFIX + "devam"))
async def resume_music(client, message):
    if not await is_admin(client, message):
        return

    await calls.resume_stream(message.chat.id)


@calls.on_stream_end()
async def on_stream_end(client, update: Update):
    global current_index

    chat_id = update.chat_id
    playlist = load_playlist()

    if not playlist:
        return

    current_index = (current_index + 1) % len(playlist)

    await calls.leave_group_call(chat_id)
    await play_track(chat_id, current_index)


# test functions


@bot.on_message(filters.command("where"))
async def where(client, message):
    chat = await client.get_chat(message.chat.id)
    await message.reply(str(chat.type))


@bot.on_message(filters.command("chatid"))
async def cid(client, message):
    await message.reply(str(message.chat.id))


@bot.on_message(filters.command("ping"))
async def ping(client, message):
    print("PING:", message.text)
    await message.reply("pong")


@bot.on_message(filters.command("voicecheck"))
async def voicecheck(client, message):
    try:
        await calls.join_group_call(message.chat.id, AudioPiped("music/Attila.mp3"))
        await message.reply("JOIN SENT")
    except Exception as e:
        await message.reply(f"ERROR: {repr(e)}")


async def main():
    try:
        print("[i] Starting app...")

        print("[i] Starting user...")
        await user.start()

        print("[i] Starting calls...")
        await calls.start()

        print("[i] Starting bot...")
        await bot.start()

        print("[i] Ready.")
        await idle()

    except Exception as e:
        print("[!] Error: ")
        print(repr(e))


if __name__ == "__main__":
    bot.run(main())
