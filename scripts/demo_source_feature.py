"""Exercise the yt-dlp source feature the way the addon does.

Run inside the tv-addons devshell:
    nix develop /home/meh/tv-addons --command python3 scripts/demo_source_feature.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import managed_runtime, ytdlp_manager  # noqa: E402

tmp = tempfile.mkdtemp()
ytdlp_manager._addon_data_dir = lambda: os.path.join(tmp, "ytdlp")


def state():
    path = ytdlp_manager._update_state_file()
    if not os.path.isfile(path):
        return {}
    with open(path) as f:
        return json.load(f)


def show(label):
    print("  %-34s installed=%s latest=%s" % (
        label,
        ytdlp_manager._read_installed_version(),
        state().get("latest_known_version"),
    ))


print("== 1. etat initial (aucun yt-dlp gere) ==")
print("  installed:", ytdlp_manager._read_installed_version())
print("  installed versions:", ytdlp_manager.list_installed_versions())

print("\n== 2. canal nightly : ensure_ytdlp_ready(allow_install=True) ==")
res = ytdlp_manager.ensure_ytdlp_ready(
    allow_install=True, requested_version="latest", source="nightly"
)
print("  ready=%s version=%s" % (res["ready"], res["version"]))
show("apres install nightly")
print("  update_state.source =", state().get("source"))

print("\n== 3. l'addon active le runtime et importe yt_dlp ==")
ytdlp_manager.activate_runtime(res["runtime_path"])
import yt_dlp  # noqa: E402

print("  sys.path[0] =", sys.path[0])
print("  yt_dlp.version =", yt_dlp.version.__version__)
print("  importe depuis   =", yt_dlp.__file__)
assert yt_dlp.version.__version__ == res["version"], "version importee != version installee"

print("\n== 4. bascule vers stable : le cache doit etre invalide ==")
res2 = ytdlp_manager.ensure_ytdlp_ready(
    allow_install=True, requested_version="latest", source="stable"
)
print("  ready=%s version=%s" % (res2["ready"], res2["version"]))
print("  update_state.source =", state().get("source"))
assert res2["version"] != res["version"], "stable == nightly, le canal n'a pas change"
show("apres bascule stable")

print("\n== 5. les deux versions coexistent sur disque ==")
print("  installed versions:", ytdlp_manager.list_installed_versions())

print("\n== 6. retour a nightly : pas de re-telechargement ==")
import time  # noqa: E402

before = os.path.getmtime(res["runtime_path"])
time.sleep(1.1)
res3 = ytdlp_manager.ensure_ytdlp_ready(
    allow_install=True, requested_version="latest", source="nightly"
)
after = os.path.getmtime(res["runtime_path"])
print("  version=%s  re-telecharge=%s" % (res3["version"], after != before))
assert res3["version"] == res["version"]
assert after == before, "le runtime nightly a ete re-telecharge alors qu'il existait"

print("\n== 7. mode sans install : signale 'missing' au lieu de telecharger ==")
ytdlp_manager._addon_data_dir = lambda: os.path.join(tmp, "vide")
res4 = ytdlp_manager.ensure_ytdlp_ready(
    allow_install=False, requested_version="latest", source="nightly"
)
print("  ready=%s reason=%s" % (res4["ready"], res4["reason"]))
assert res4["reason"] == "missing"

print("\nOK — parcours complet valide")
