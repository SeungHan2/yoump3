import os
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, quote
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from dotenv import load_dotenv
import xml.etree.ElementTree as ET

load_dotenv()

MP3_DIR = os.path.join(os.getcwd(), "mp3")
FEED_PATH = os.path.join(os.getcwd(), "feed.xml")

BASE_URL = os.getenv("BASE_URL", "").strip()
FEED_TITLE = os.getenv("FEED_TITLE", "My Private Audio Feed")
FEED_DESCRIPTION = os.getenv("FEED_DESCRIPTION", "Personal audio archive for offline listening.")
FEED_AUTHOR = os.getenv("FEED_AUTHOR", "Me")
FEED_IMAGE_URL = os.getenv("FEED_IMAGE_URL", "").strip()

if not BASE_URL:
    raise SystemExit("Please set BASE_URL in .env (must end with a slash).")
if not BASE_URL.endswith("/"):
    BASE_URL += "/"

def rfc2822(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")

items = []
for fn in sorted(os.listdir(MP3_DIR), reverse=True):
    if not fn.lower().endswith(".mp3"):
        continue
    path = os.path.join(MP3_DIR, fn)
    try:
        audio = MP3(path)
        tags = EasyID3(path)
    except Exception:
        audio = MP3(path)
        tags = {}
    title = tags.get("title", [os.path.splitext(fn)[0]])[0]
    artist = tags.get("artist", [""])[0]
    size = os.path.getsize(path)
    mtime = os.path.getmtime(path)

    # Build full URL (ensure URL-safe filename)
    url = urljoin(BASE_URL, f"mp3/{quote(fn)}")

    items.append({
        "title": title,
        "author": artist or FEED_AUTHOR,
        "url": url,
        "length": str(size),
        "pubDate": rfc2822(mtime),
        "guid": url,  # simple, stable GUID
    })

# Build RSS
rss = ET.Element("rss", version="2.0", attrib={
    "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"
})
channel = ET.SubElement(rss, "channel")
ET.SubElement(channel, "title").text = FEED_TITLE
ET.SubElement(channel, "link").text = BASE_URL
ET.SubElement(channel, "description").text = FEED_DESCRIPTION
ET.SubElement(channel, "language").text = "ko-KR"
ET.SubElement(channel, "itunes:author").text = FEED_AUTHOR
if FEED_IMAGE_URL:
    image = ET.SubElement(channel, "image")
    ET.SubElement(image, "url").text = FEED_IMAGE_URL

now_ts = time.time()
ET.SubElement(channel, "lastBuildDate").text = datetime.utcfromtimestamp(now_ts).strftime("%a, %d %b %Y %H:%M:%S +0000")

for it in items:
    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = it["title"]
    ET.SubElement(item, "guid").text = it["guid"]
    ET.SubElement(item, "pubDate").text = it["pubDate"]
    e = ET.SubElement(item, "enclosure", attrib={
        "url": it["url"],
        "length": it["length"],
        "type": "audio/mpeg"
    })
    ET.SubElement(item, "itunes:author").text = it["author"]

# Write XML
tree = ET.ElementTree(rss)
ET.indent(tree, space="  ")
tree.write(FEED_PATH, encoding="utf-8", xml_declaration=True)

print(f"[ok] Wrote {FEED_PATH}. Upload this file and the 'mp3/' folder to your host so URLs match BASE_URL.")
