"""Prove the installed nightly yt-dlp actually works against YouTube.

Run in the tv-addons devShell (which provides deno + ffmpeg):
    nix develop /home/meh/tv-addons --command python3 scripts/check_youtube_extract.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import ytdlp_manager  # noqa: E402

tmp = tempfile.mkdtemp()
ytdlp_manager._addon_data_dir = lambda: os.path.join(tmp, "ytdlp")

latest = ytdlp_manager._resolve_latest_version(force_refresh=True, source="nightly")
runtime_path = ytdlp_manager._download_and_install(latest, source="nightly")
print("installe : nightly %s" % latest)

ytdlp_manager.activate_runtime(runtime_path)
import yt_dlp  # noqa: E402

print("importe  : %s" % yt_dlp.version.__version__)
assert yt_dlp.version.__version__ == latest

URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"  # Big Buck Bunny, stable id

# Same options the addon builds (js runtime for the JS challenges).
opts = {
    "quiet": True,
    "no_warnings": False,
    "extract_flat": False,
    "js_runtimes": {"deno": {}},
    "remote_components": {"ejs:github"},
}

with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info(URL, download=False)

print("titre    : %s" % info.get("title"))
print("duree    : %ss" % info.get("duration"))

formats = info.get("formats") or []
audio = [f for f in formats if f.get("acodec") not in (None, "none")]
video = [f for f in formats if f.get("vcodec") not in (None, "none")]
print("formats  : %d au total, %d video, %d audio" % (len(formats), len(video), len(audio)))

for f in audio[:4]:
    print("   audio: id=%-10s ext=%-5s acodec=%-8s abr=%s" % (
        f.get("format_id"), f.get("ext"), f.get("acodec"), f.get("abr")))

assert formats, "aucun format retourne"
assert audio, "aucune piste audio"
print("\nOK — le paquet nightly installe extrait reellement YouTube")
