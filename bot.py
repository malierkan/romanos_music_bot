# musicbot_tgcaller.py
import os
import json
import asyncio
import sys
import logging
import inspect
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pyrogram.enums import ChatMemberStatus

# tgcaller
from tgcaller import TgCaller

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("musicbot")

logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger("tgcaller").setLevel(logging.DEBUG)
logging.getLogger("pyrogram").setLevel(logging.INFO)


API_ID = int(os.getenv("API_ID") or 0)
API_HASH = os.getenv("API_HASH") or None
BOT_TOKEN = os.getenv("BOT_TOKEN") or None
SESSION = os.getenv("SESSION")  # optional: string session

# --- Clients
# bot client (for commands / messages). BOT_TOKEN optional but useful.
if BOT_TOKEN:
    bot = Client("musicbot-bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
else:
    # if user prefers not to use bot token, bot can be same as user (but recommended to keep both)
    bot = Client("musicbot-bot", api_id=API_ID, api_hash=API_HASH)

# user client: must be a user account (string session or interactive session file)
if SESSION:
    user = Client(
        "musicbot-user", api_id=API_ID, api_hash=API_HASH, session_string=SESSION
    )
else:
    # will create or use ./musicbot-user.session file; interactive on first run
    user = Client("musicbot-user", api_id=API_ID, api_hash=API_HASH)

# caller bound to user
caller = TgCaller(user)

# config
PLAYLIST_FILE = "playlist.json"
MUSIC_FOLDER = "music"
PREFIX = "m"
DELAY = 2

current_index = 0
current_message_id = None

# --- try flexible imports for MediaStream / types if available
MediaStream = None
StreamType = None
AudioConfig = None
try:
    from tgcaller.types import MediaStream, StreamType, AudioConfig

    log.info("Imported MediaStream / StreamType from tgcaller.types")
except Exception:
    try:
        from tgcaller.types.media_stream import MediaStream
        from tgcaller.types.stream_type import StreamType

        log.info("Imported MediaStream / StreamType from tgcaller.types.*")
    except Exception:
        log.info("tgcaller types not found (fallback mode)")


# helpers
def load_playlist():
    log.info("[i] Opening playlist...")
    with open(PLAYLIST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return sorted(data, key=lambda x: x["id"])


async def is_admin(client, message):
    log.info("[i] Checking for priviliges...")
    if not message.from_user:
        return False
    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    log.debug(member)
    if member.status == ChatMemberStatus.OWNER:
        return True
    if member.status == ChatMemberStatus.ADMINISTRATOR:
        if member.privileges:
            return member.privileges.can_manage_video_chats
        log.info("[i] Member is approved.")
        return True
    await message.reply(
        "❌ Bu komutu kullanmak için sesli sohbet yönetme yetkisine sahip olmalısın."
    )
    log.info("[i] Member is not approved.")
    return False


async def send_info(client, chat_id, track):
    global current_message_id
    name = track["isim"].replace(".mp3", "")
    text = f"🎵 **{name}** ({track.get('yil','')})\n\n{track.get('aciklama','')}"
    if current_message_id:
        try:
            log.info("[i] Deleting old messages...")
            await client.delete_messages(chat_id, current_message_id)
        except Exception:
            pass
    log.info("[i] Sending info...")
    msg = await client.send_message(chat_id, text)
    current_message_id = msg.id


def _caller_has(*names):
    for n in names:
        if hasattr(caller, n):
            return n
    return None


async def _maybe_call(obj, name, *args, **kwargs):
    """
    Call a method that might be sync or async. Return result.
    """
    meth = getattr(obj, name)
    res = meth(*args, **kwargs)
    if inspect.isawaitable(res):
        return await res
    return res


async def _caller_join_and_play(chat_id, path):
    """
    Robust join+play wrapper supporting multiple tgcaller API variants.
    Tries variants in order: (join_call + play), (join + play), (start_call), (play only), (join_group_call fallback)
    """
    path = os.path.abspath(path)
    log.info("VOICE PATH: %s", path)
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    # 1) join_call + play
    if _caller_has("join_call") and _caller_has("play"):
        log.info("Using caller.join_call + caller.play")
        await _maybe_call(caller, "join_call", chat_id)
        await _maybe_call(caller, "play", chat_id, path)
        return "join_call+play"

    # 2) join + play
    if _caller_has("join") and _caller_has("play"):
        log.info("Using caller.join + caller.play")
        await _maybe_call(caller, "join", chat_id)
        await _maybe_call(caller, "play", chat_id, path)
        return "join+play"

    # 3) start_call (accepting MediaStream or path)
    if _caller_has("start_call"):
        log.info("Using caller.start_call (attempt)")
        try:
            if MediaStream:
                stream = None
                try:
                    # try common ctor names
                    stream = MediaStream(file_path=path)
                except Exception:
                    try:
                        stream = MediaStream(path)
                    except Exception:
                        stream = None
                if stream:
                    await _maybe_call(caller, "start_call", chat_id, stream)
                else:
                    await _maybe_call(caller, "start_call", chat_id, path)
            else:
                await _maybe_call(caller, "start_call", chat_id, path)
            return "start_call"
        except Exception as e:
            log.warning("start_call failed: %s", e)

    # 4) play only (may auto-join)
    if _caller_has("play"):
        log.info("Using caller.play (may auto-join)")
        await _maybe_call(caller, "play", chat_id, path)
        return "play"

    # 5) fallback join_group_call
    if _caller_has("join_group_call"):
        log.info("Using caller.join_group_call (fallback)")
        await _maybe_call(caller, "join_group_call", chat_id, path)
        return "join_group_call"

    raise RuntimeError("No supported join/play API found on caller")


async def play_track(chat_id, index):
    global current_index
    try:
        playlist = load_playlist()
        if not playlist:
            log.info("[i] Playlist is empty.")
            await bot.send_message(chat_id, "❌ Playlist boş.")
            return

        track = playlist[index]
        path = os.path.join(MUSIC_FOLDER, track["isim"])
        log.info("[i] Playlist is loaded. path=%s", path)

        if not os.path.exists(path):
            log.info("[i] Music file doesn't exist.")
            await bot.send_message(chat_id, f"❌ Dosya yok: {path}")
            return

        # try leaving
        try:
            leave_method = _caller_has("leave", "leave_call", "leave_group_call")
            if leave_method:
                await _maybe_call(caller, leave_method, chat_id)
        except Exception:
            pass

        log.info("[i] Attempting to join/play...")
        try:
            used = await _caller_join_and_play(chat_id, path)
            log.info("[i] Stream method used: %s", used)
            await asyncio.sleep(DELAY)
            log.info("[i] Call is active.")
        except Exception as e:
            log.exception("VOICE ERROR:")
            await bot.send_message(chat_id, f"VOICE ERROR: {repr(e)}")
            return

        await send_info(bot, chat_id, track)
    except Exception as e:
        log.exception("Unhandled play_track error")
        await bot.send_message(chat_id, f"Unhandled error: {repr(e)}")


# --- listeners
@bot.on_message(filters.command(PREFIX + "baslat", prefixes="/"))
async def start_music(client, message):
    global current_index
    if not await is_admin(client, message):
        return

    me = await client.get_chat_member(message.chat.id, (await client.get_me()).id)
    if me.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        await message.reply("❌ Bot admin değil.")
        return

    await play_track(message.chat.id, current_index)


@bot.on_message(filters.command(PREFIX + "sonraki", prefixes="/"))
async def next_music(client, message):
    global current_index
    if not await is_admin(client, message):
        return
    playlist = load_playlist()
    current_index = (current_index + 1) % len(playlist)
    try:
        leave_method = _caller_has("leave", "leave_call", "leave_group_call")
        if leave_method:
            await _maybe_call(caller, leave_method, message.chat.id)
    except Exception:
        pass
    await play_track(message.chat.id, current_index)


@bot.on_message(filters.command(PREFIX + "onceki", prefixes="/"))
async def prev_music(client, message):
    global current_index
    if not await is_admin(client, message):
        return
    playlist = load_playlist()
    current_index = (current_index - 1) % len(playlist)
    try:
        leave_method = _caller_has("leave", "leave_call", "leave_group_call")
        if leave_method:
            await _maybe_call(caller, leave_method, message.chat.id)
    except Exception:
        pass
    await play_track(message.chat.id, current_index)


@bot.on_message(filters.command(PREFIX + "dur", prefixes="/"))
async def stop_music(client, message):
    if not await is_admin(client, message):
        return
    leave_method = _caller_has("leave", "leave_call", "leave_group_call")
    if leave_method:
        await _maybe_call(caller, leave_method, message.chat.id)


@bot.on_message(filters.command(PREFIX + "sozler", prefixes="/"))
async def lyrics(client, message):
    playlist = load_playlist()
    track = playlist[current_index]
    await send_info(client, message.chat.id, track)


@bot.on_message(filters.command(PREFIX + "duraklat", prefixes="/"))
async def pause_music(client, message):
    if not await is_admin(client, message):
        return
    pause_m = _caller_has("pause")
    if pause_m:
        await _maybe_call(caller, pause_m, message.chat.id)


@bot.on_message(filters.command(PREFIX + "devam", prefixes="/"))
async def resume_music(client, message):
    if not await is_admin(client, message):
        return
    resume_m = _caller_has("resume")
    if resume_m:
        await _maybe_call(caller, resume_m, message.chat.id)


# tests
@bot.on_message(filters.command("ping", prefixes="/"))
async def ping(client, message):
    await message.reply("pong")


@bot.on_message(filters.command("voicecheck", prefixes="/"))
async def voicecheck(client, message):
    try:
        path = os.path.abspath("music/Attila.mp3")
        used = await _caller_join_and_play(message.chat.id, path)
        await message.reply(f"JOIN SENT, method={used}")
    except Exception as e:
        await message.reply(f"ERROR: {repr(e)}")


@bot.on_message(filters.command("whoami", prefixes="/"))
async def whoami(_, m):
    # print user client identity
    u = await user.get_me()
    await m.reply(
        f"user: {u.first_name} id:{u.id} is_bot:{getattr(u,'is_bot',False)} username:{getattr(u,'username',None)}"
    )
    # show user membership in this chat
    try:
        cm = await user.get_chat_member(m.chat.id, u.id)
        await m.reply(
            f"chat member status: {cm.status} privileges: {getattr(cm,'privileges',None)}"
        )
    except Exception as e:
        await m.reply(f"get_chat_member error: {repr(e)}")


@bot.on_message(filters.command("whoami2", prefixes="/"))
async def whoami2(_, m):
    bot_me = await bot.get_me()
    user_me = await user.get_me()
    await m.reply(
        f"bot: id={bot_me.id} is_bot={getattr(bot_me,'is_bot',None)} username={getattr(bot_me,'username',None)}"
    )
    await m.reply(
        f"user: id={user_me.id} is_bot={getattr(user_me,'is_bot',None)} username={getattr(user_me,'username',None)}"
    )


@bot.on_message(filters.command("chatinfo", prefixes="/"))
async def chatinfo(_, m):
    chat = await bot.get_chat(m.chat.id)
    await m.reply(str(chat))
    # Also check chat type
    await m.reply(
        f"type: {chat.type} id: {chat.id} title: {getattr(chat,'title',None)}"
    )


@bot.on_message(filters.command("callerinfo", prefixes="/"))
async def callerinfo(_, m):
    await m.reply(
        "caller dir: " + ", ".join([x for x in dir(caller) if not x.startswith("_")])
    )
    try:
        # try some common inspector methods safely
        if hasattr(caller, "client"):
            await m.reply(f"caller.client: {getattr(caller,'client')}")
        # try to call a list/get function if exists
        for name in (
            "get_calls",
            "list_calls",
            "calls",
            "active_calls",
            "get_active_calls",
        ):
            if hasattr(caller, name):
                try:
                    val = await _maybe_call(caller, name)
                    await m.reply(f"{name}: {val}")
                except Exception as e:
                    await m.reply(f"{name} error: {repr(e)}")
    except Exception as e:
        await m.reply(f"inspect error: {repr(e)}")


# main
async def main():
    try:
        log.info("[i] Starting user...")
        await user.start()

        # verify user is a real user account (not bot)
        me_user = await user.get_me()
        if getattr(me_user, "is_bot", False):
            log.critical(
                "User client is a bot account. Voice requires a real user account. Stop."
            )
            print(
                "ERROR: user client is a bot. Use a real user account (string session) for voice."
            )
            # stop gracefully
            await user.stop()
            return

        log.info("[i] Starting caller...")
        start_method = _caller_has("start", "start_service", "start_client")
        if start_method:
            await _maybe_call(caller, start_method)

        log.info("[i] Starting bot...")
        await bot.start()

        log.info("[i] Ready.")
        await idle()
    except Exception as e:
        log.exception("Startup error:")
    finally:
        try:
            stop_method = _caller_has("stop", "stop_service")
            if stop_method:
                await _maybe_call(caller, stop_method)
        except Exception:
            pass
        try:
            await user.stop()
            await bot.stop()
        except Exception:
            pass


if __name__ == "__main__":
    # use pyrogram runner to avoid loop conflicts
    bot.run(main())
