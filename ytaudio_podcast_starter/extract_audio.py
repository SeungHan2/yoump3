import os
import sys
import re
from datetime import datetime
from typing import List
import yt_dlp
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
from mutagen.mp3 import MP3

OUTDIR = os.path.join(os.getcwd(), "mp3")
os.makedirs(OUTDIR, exist_ok=True)

def load_urls_from_file(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    urls = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    return urls

def safe_name(name: str) -> str:
    name = re.sub(r"[\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180]

def download_to_mp3(url: str, bitrate: str = None):
    # Prepare ydl options
    mp3_bitrate = (bitrate or os.environ.get("MP3_BITRATE") or "160k")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(OUTDIR, "%(title).200B [%(id)s].%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": mp3_bitrate.replace("k",""),
            }
        ],
        "postprocessor_args": [
            "-ar", "44100",
        ],
        "quiet": False,
        "noprogress": False,
        "ignoreerrors": True,
        "writethumbnail": True,
        "nooverwrites": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # After conversion, set ID3 tags
    if not info:
        print(f"[skip] Could not retrieve info for: {url}")
        return

    title = info.get("title") or "Unknown Title"
    uploader = info.get("uploader") or info.get("channel") or ""
    upload_date = info.get("upload_date")  # YYYYMMDD
    video_id = info.get("id") or ""
    thumb = None
    # yt-dlp typically saves thumbnail alongside original before conversion; try to locate
    possible_bases = [
        os.path.join(OUTDIR, f"{title} [{video_id}]"),
        os.path.join(OUTDIR, f"{safe_name(title)} [{video_id}]"),
    ]
    for base in possible_bases:
        for ext in (".jpg",".jpeg",".png",".webp"):
            p = base + ext
            if os.path.exists(p):
                thumb = p
                break

    # Locate mp3 file
    # After postprocessing, output name will be same base but .mp3
    mp3_candidates = []
    for base in possible_bases:
        p = base + ".mp3"
        if os.path.exists(p):
            mp3_candidates.append(p)
    if not mp3_candidates:
        # fallback: search OUTDIR for file ending with [id].mp3
        for fn in os.listdir(OUTDIR):
            if fn.endswith(".mp3") and f"[{video_id}]" in fn:
                mp3_candidates.append(os.path.join(OUTDIR, fn))
    if not mp3_candidates:
        print(f"[warn] MP3 not found for: {title}")
        return
    mp3_path = mp3_candidates[0]

    # Apply tags
    try:
        audio = MP3(mp3_path, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
        easy = EasyID3(mp3_path)
        easy["title"] = title
        if uploader:
            easy["artist"] = uploader
            easy["albumartist"] = uploader
        easy["album"] = uploader or "YouTube"
        if upload_date and len(upload_date)==8:
            y = upload_date[:4]
            easy["date"] = y
            easy["originaldate"] = upload_date
        easy.save()

        if thumb and os.path.exists(thumb):
            with open(thumb, "rb") as f:
                img_data = f.read()
            audio.tags.add(APIC(
                encoding=3,
                mime="image/jpeg",
                type=3, desc="Cover",
                data=img_data
            ))
            audio.save()
    except Exception as e:
        print(f"[warn] tagging failed for {mp3_path}: {e}")

    # Finally, rename to a simple, safe filename
    simple_name = f"{safe_name(title)} [{video_id}].mp3"
    final_path = os.path.join(OUTDIR, simple_name)
    if mp3_path != final_path:
        try:
            if not os.path.exists(final_path):
                os.replace(mp3_path, final_path)
            else:
                # already exists; keep existing
                pass
        except Exception as e:
            print(f"[warn] rename failed: {e}")

    print(f"[ok] {simple_name}")


def main():
    args = sys.argv[1:]
    urls = args if args else load_urls_from_file("urls.txt")
    if not urls:
        print("No URLs. Put links in urls.txt or pass as arguments.")
        return
    bitrate = os.environ.get("MP3_BITRATE")
    for url in urls:
        download_to_mp3(url, bitrate=bitrate)

if __name__ == "__main__":
    main()
