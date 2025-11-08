import asyncio
import os
import re
import json
from typing import Union
import requests
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from BRANDEDKING.utils.database import is_on_off
from BRANDEDKING import app
from BRANDEDKING.utils.formatters import time_to_seconds
import random
import logging
import aiohttp
from ShrutiMusic import LOGGER
from urllib.parse import urlparse

YOUR_API_URL = None

def cookie_txt_file():
    cookie_dir = "ShrutiMusic/cookies"
    if not os.path.exists(cookie_dir):
        return None
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    if not cookies_files:
        return None
    cookie_file = os.path.join(cookie_dir, random.choice(cookies_files))
    return cookie_file

async def load_api_url():
    global YOUR_API_URL
    logger = LOGGER("ShrutiMusic/platforms/Youtube.py")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://pastebin.com/raw/rLsBhAQa") as response:
                if response.status == 200:
                    content = await response.text()
                    YOUR_API_URL = content.strip()
                    logger.info(f"API URL loaded successfully")
                else:
                    logger.error(f"Failed to fetch API URL. HTTP Status: {response.status}")
    except Exception as e:
        logger.error(f"Error loading API URL: {e}")

try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.create_task(load_api_url())
    else:
        loop.run_until_complete(load_api_url())
except RuntimeError:
    pass

async def get_telegram_file(telegram_link: str, video_id: str, file_type: str) -> str:
    """
    Telegram link se file download
    """
    logger = LOGGER("ShrutiMusic/platforms/Youtube.py")
    try:
        extension = ".webm" if file_type == "audio" else ".mkv"
        file_path = os.path.join("downloads", f"{video_id}{extension}")
        
        # Agar already exist kare to seedha return
        if os.path.exists(file_path):
            logger.info(f"📂 [LOCAL] File exists: {video_id}")
            return file_path
        
        # Parse Telegram link: https://t.me/channelname/messageid
        parsed = urlparse(telegram_link)
        parts = parsed.path.strip("/").split("/")
        
        if len(parts) < 2:
            logger.error(f"❌ Invalid Telegram link format: {telegram_link}")
            return None
            
        channel_name = parts[0]
        message_id = int(parts[1])
        
        logger.info(f"📥 [TELEGRAM] Downloading from @{channel_name}/{message_id}")
        
        # Pyrogram se message fetch karke download
        msg = await app.get_messages(channel_name, message_id)
        
        os.makedirs("downloads", exist_ok=True)
        await msg.download(file_name=file_path)
        
        # Wait karo jab tak file fully download na ho
        timeout = 0
        while not os.path.exists(file_path) and timeout < 60:
            await asyncio.sleep(0.5)
            timeout += 0.5
        
        if os.path.exists(file_path):
            logger.info(f"✅ [TELEGRAM] Downloaded: {video_id}")
            return file_path
        else:
            logger.error(f"❌ [TELEGRAM] Timeout: {video_id}")
            return None
        
    except Exception as e:
        logger.error(f"❌ [TELEGRAM] Failed to download {video_id}: {e}")
        return None

async def download_song(link: str) -> str:
    global YOUR_API_URL
    
    if not YOUR_API_URL:
        await load_api_url()
        if not YOUR_API_URL:
            logger = LOGGER("ShrutiMusic/platforms/Youtube.py")
            logger.error("API URL not available")
            return None
    
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link
    logger = LOGGER("ShrutiMusic/platforms/Youtube.py")
    logger.info(f"🎵 [AUDIO] Starting download for: {video_id}")

    if not video_id or len(video_id) < 3:
        return None

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.webm")

    # Local check
    if os.path.exists(file_path):
        logger.info(f"🎵 [LOCAL] File exists: {video_id}")
        return file_path

    try:
        async with aiohttp.ClientSession() as session:
            params = {"url": video_id, "type": "audio"}
            
            async with session.get(
                f"{YOUR_API_URL}/download",
                params=params,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                data = await response.json()

                if response.status != 200:
                    logger.error(f"[AUDIO] API error: {response.status}")
                    return None

                # Format 1: Direct Telegram link (already uploaded)
                if data.get("link") and "t.me" in str(data.get("link")):
                    telegram_link = data["link"]
                    logger.info(f"🔗 [AUDIO] Telegram link received: {telegram_link}")
                    
                    # Telegram se download karo
                    downloaded_file = await get_telegram_file(telegram_link, video_id, "audio")
                    if downloaded_file:
                        return downloaded_file
                    else:
                        logger.warning(f"⚠️ [AUDIO] Telegram download failed")
                        return None
                
                # Format 2: Stream URL (not yet uploaded)
                elif data.get("status") == "success" and data.get("stream_url"):
                    stream_url = data["stream_url"]
                    logger.info(f"[AUDIO] Stream URL obtained: {video_id}")
                    
                    # Download from stream URL
                    async with session.get(
                        stream_url,
                        timeout=aiohttp.ClientTimeout(total=300)
                    ) as file_response:
                        if file_response.status != 200:
                            logger.error(f"[AUDIO] Download failed: {file_response.status}")
                            return None
                            
                        with open(file_path, "wb") as f:
                            async for chunk in file_response.content.iter_chunked(16384):
                                f.write(chunk)
                        
                        logger.info(f"🎉 [AUDIO] Downloaded: {video_id}")
                        return file_path
                else:
                    logger.error(f"[AUDIO] Invalid response: {data}")
                    return None

    except asyncio.TimeoutError:
        logger.error(f"[AUDIO] Timeout: {video_id}")
        return None
    except Exception as e:
        logger.error(f"[AUDIO] Exception: {video_id} - {e}")
        return None


async def download_video(link: str) -> str:
    global YOUR_API_URL
    
    if not YOUR_API_URL:
        await load_api_url()
        if not YOUR_API_URL:
            logger = LOGGER("ShrutiMusic/platforms/Youtube.py")
            logger.error("API URL not available")
            return None
    
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link
    logger = LOGGER("ShrutiMusic/platforms/Youtube.py")
    logger.info(f"🎥 [VIDEO] Starting download for: {video_id}")

    if not video_id or len(video_id) < 3:
        return None

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mkv")

    # Local check
    if os.path.exists(file_path):
        logger.info(f"🎥 [LOCAL] File exists: {video_id}")
        return file_path

    try:
        async with aiohttp.ClientSession() as session:
            params = {"url": video_id, "type": "video"}
            
            async with session.get(
                f"{YOUR_API_URL}/download",
                params=params,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                data = await response.json()

                if response.status != 200:
                    logger.error(f"[VIDEO] API error: {response.status}")
                    return None

                # Format 1: Direct Telegram link (already uploaded)
                if data.get("link") and "t.me" in str(data.get("link")):
                    telegram_link = data["link"]
                    logger.info(f"🔗 [VIDEO] Telegram link received: {telegram_link}")
                    
                    # Telegram se download karo
                    downloaded_file = await get_telegram_file(telegram_link, video_id, "video")
                    if downloaded_file:
                        return downloaded_file
                    else:
                        logger.warning(f"⚠️ [VIDEO] Telegram download failed")
                        return None
                
                # Format 2: Stream URL (not yet uploaded)
                elif data.get("status") == "success" and data.get("stream_url"):
                    stream_url = data["stream_url"]
                    logger.info(f"[VIDEO] Stream URL obtained: {video_id}")
                    
                    # Download from stream URL
                    async with session.get(
                        stream_url,
                        timeout=aiohttp.ClientTimeout(total=600)
                    ) as file_response:
                        if file_response.status != 200:
                            logger.error(f"[VIDEO] Download failed: {file_response.status}")
                            return None
                            
                        with open(file_path, "wb") as f:
                            async for chunk in file_response.content.iter_chunked(16384):
                                f.write(chunk)
                        
                        logger.info(f"🎉 [VIDEO] Downloaded: {video_id}")
                        return file_path
                else:
                    logger.error(f"[VIDEO] Invalid response: {data}")
                    return None

    except asyncio.TimeoutError:
        logger.error(f"[VIDEO] Timeout: {video_id}")
        return None
    except Exception as e:
        logger.error(f"[VIDEO] Exception: {video_id} - {e}")
        return None

async def check_file_size(link):
    async def get_format_info(link):
        cookie_file = cookie_txt_file()
        if not cookie_file:
            print("No cookies found. Cannot check file size.")
            return None
            
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_file,
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f'Error:\n{stderr.decode()}')
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    
    formats = info.get('formats', [])
    if not formats:
        print("No formats found.")
        return None
    
    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            else:
                return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return []
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_file} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = [key for key in playlist.split("\n") if key]
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return [], link
        ytdl_opts = {"quiet": True, "cookiefile": cookie_file}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    if "dash" not in str(format["format"]).lower():
                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format.get("filesize"),
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format["format_note"],
                                "yturl": link,
                            }
                        )
                except:
                    continue
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link

        try:
            if songvideo or songaudio:
                downloaded_file = await download_song(link)
                if downloaded_file:
                    return downloaded_file, True
                else:
                    return None, False
            elif video:
                downloaded_file = await download_video(link)
                if downloaded_file:
                    return downloaded_file, True
                else:
                    return None, False
            else:
                downloaded_file = await download_song(link)
                if downloaded_file:
                    return downloaded_file, True
                else:
                    return None, False
        except Exception as e:
            print(f"Download failed: {e}")
            return None, False
