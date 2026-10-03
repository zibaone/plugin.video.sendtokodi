"""Download a real YouTube audio stream and verify it decodes.

This closes the gap between "extraction returns formats" and "the media is
actually playable": the URL handed to InputStreamAdaptive must be fetchable
and decodable.

Run in the tv-addons devShell with deno on PATH:
    nix develop /home/meh/tv-addons --command python3 scripts/check_youtube_playable.py
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import ytdlp_manager  # noqa: E402

tmp = tempfile.mkdtemp()
ytdlp_manager._addon_data_dir = lambda: os.path.join(tmp, "ytdlp")

latest = ytdlp_manager._resolve_latest_version(force_refresh=True, source="nightly")
runtime_path = ytdlp_manager._download_and_install(latest, source="nightly")
ytdlp_manager.activate_runtime(runtime_path)
import yt_dlp  # noqa: E402

print("yt-dlp nightly %s" % yt_dlp.version.__version__)

URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
outdir = os.path.join(tmp, "dl")

opts = {
    "quiet": True,
    "js_runtimes": {"deno": {}},
    "remote_components": {"ejs:github"},
    "format": "worstaudio[ext=m4a]/worstaudio",
    "outtmpl": os.path.join(outdir, "%(id)s.%(ext)s"),
    "noplaylist": True,
}

with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info(URL, download=True)

files = os.listdir(outdir)
print("telecharge : %s" % files)
assert files, "aucun fichier telecharge"

path = os.path.join(outdir, files[0])
size = os.path.getsize(path)
print("taille     : %.1f KiB" % (size / 1024))
assert size > 10_000, "fichier suspicieusement petit"

# ffprobe: the media must be a real, decodable stream.
probe = subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "a:0",
     "-show_entries", "stream=codec_name,channels,sample_rate,duration",
     "-of", "default=noprint_wrappers=1", path],
    capture_output=True, text=True,
)
print("ffprobe    :")
for line in probe.stdout.strip().splitlines():
    print("   %s" % line)
assert probe.returncode == 0, probe.stderr
assert "codec_name=" in probe.stdout, "ffprobe n'a trouve aucun flux audio"

print("\nOK — la piste audio est telechargeable et decodable (le maillon ISA est valide)")
