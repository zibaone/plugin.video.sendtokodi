#!/usr/bin/env bash
#
# Throwaway Kodi instance for developing plugin.video.sendtokodi.
#
# Never touches ~/.kodi. Everything lives in .kodi-local/ inside the repo.
# Kodi's own bundled addons (inputstream.adaptive, inputstreamhelper,
# script.module.requests, ...) come from the Nix wrapper, so only the plugin
# under development is linked into the profile.
#
# Usage:
#   scripts/run_local_kodi.sh [--clean] [--prepare-only] [--headless] [kodi args]
#
# Options:
#   --clean         Wipe .kodi-local/ first
#   --prepare-only  Build the profile and exit (no Kodi)
#   --headless      Run under Xvfb (no window); implies a private display
#   --port N        JSON-RPC port (default 8082)
#   -h, --help

set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
KODI_HOME="${BASE_DIR}/.kodi-local"
ADDONS_DIR="${KODI_HOME}/.kodi/addons"
USERDATA_DIR="${KODI_HOME}/.kodi/userdata"
DATABASE_DIR="${USERDATA_DIR}/Database"

ADDON_ID="plugin.video.sendtokodi"
PORT="${KODI_JSONRPC_PORT:-18082}"
DISPLAY_NUM="${KODI_DISPLAY_NUM:-99}"

CLEAN=false
PREPARE_ONLY=false
HEADLESS=false
KODI_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean) CLEAN=true; shift ;;
    --prepare-only) PREPARE_ONLY=true; shift ;;
    --headless) HEADLESS=true; shift ;;
    --port) PORT="$2"; shift 2 ;;
    -h|--help)
      sed -n '3,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) KODI_ARGS+=("$1"); shift ;;
  esac
done

if [ "$CLEAN" = true ] && [ -d "$KODI_HOME" ]; then
  echo "Cleaning ${KODI_HOME}..."
  rm -rf "$KODI_HOME"
fi

echo "Preparing Kodi profile (${KODI_HOME})..."
mkdir -p "$ADDONS_DIR" "$USERDATA_DIR" "$DATABASE_DIR"

# 1. The plugin under development, linked live.
ln -sfn "${BASE_DIR}" "${ADDONS_DIR}/${ADDON_ID}"
echo "   linked ${ADDON_ID} -> ${BASE_DIR}"

# 2. Declare the addon as enabled, otherwise Kodi will not load it.
ADDONS_DB="${DATABASE_DIR}/Addons37.db"
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$ADDONS_DB" << SQL
CREATE TABLE IF NOT EXISTS version (id text, version integer);
INSERT OR IGNORE INTO version (id, version) VALUES ('Addons37.db', 37);
CREATE TABLE IF NOT EXISTS installed (addonID text primary key, enabled integer, installDate text, lastUpdated text, lastUsed text, origin text);
INSERT OR REPLACE INTO installed (addonID, enabled) VALUES ('${ADDON_ID}', 1);
INSERT OR REPLACE INTO installed (addonID, enabled) VALUES ('inputstream.adaptive', 1);
INSERT OR REPLACE INTO installed (addonID, enabled) VALUES ('script.module.inputstreamhelper', 1);
INSERT OR REPLACE INTO installed (addonID, enabled) VALUES ('script.module.requests', 1);
SQL
  echo "   enabled in Addons37.db"
else
  echo "   WARNING: sqlite3 not on PATH, the addon may not load"
fi

# 3. Web server for JSON-RPC, so the instance can be driven from outside.
#    Kodi 21 reads these from guisettings.xml (userdata), not from
#    advancedsettings.xml, so write guisettings.xml directly.
GUISETTINGS="${USERDATA_DIR}/guisettings.xml"
if [ ! -f "$GUISETTINGS" ]; then
  cat << XML > "$GUISETTINGS"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<settings version="2">
    <setting id="services.webserver">true</setting>
    <setting id="services.webserverport">${PORT}</setting>
    <setting id="services.esallinterfaces">true</setting>
    <setting id="services.webserverauthentication">false</setting>
    <setting id="services.webserverssl">false</setting>
</settings>
XML
  echo "   JSON-RPC on port ${PORT} (guisettings.xml)"
fi

# Keep the log verbose enough to diagnose addon problems.
ADVANCED="${USERDATA_DIR}/advancedsettings.xml"
if [ ! -f "$ADVANCED" ]; then
  cat << XML > "$ADVANCED"
<advancedsettings version="1.0">
  <loglevel>1</loglevel>
</advancedsettings>
XML
fi

# 4. Default the new setting to nightly so the feature is exercised.
ADDON_DATA="${USERDATA_DIR}/addon_data/${ADDON_ID}"
mkdir -p "$ADDON_DATA"
if [ ! -f "${ADDON_DATA}/settings.xml" ]; then
  cat << XML > "${ADDON_DATA}/settings.xml"
<settings version="2">
    <setting id="ytdlp_source">nightly</setting>
</settings>
XML
  echo "   ytdlp_source defaulted to 'nightly'"
fi

if [ "$PREPARE_ONLY" = true ]; then
  echo "Profile ready: ${KODI_HOME}"
  exit 0
fi

KODI_BIN="${KODI_BIN:-kodi}"
if ! command -v "$KODI_BIN" >/dev/null 2>&1; then
  KODI_BIN="$(find /nix/store -maxdepth 4 -name kodi -path '*/bin/kodi' 2>/dev/null | head -1)"
fi

if [ "$HEADLESS" = true ]; then
  if ! command -v Xvfb >/dev/null 2>&1; then
    echo "ERROR: --headless needs Xvfb" >&2
    exit 1
  fi
  export DISPLAY=":${DISPLAY_NUM}"
  echo "Starting Xvfb on ${DISPLAY}..."
  Xvfb "$DISPLAY" -screen 0 1280x720x24 >/dev/null 2>&1 &
  XVFB_PID=$!
  trap 'kill "$XVFB_PID" 2>/dev/null || true' EXIT
  # Give the server a moment to accept connections.
  for _ in $(seq 1 20); do
    [ -e "/tmp/.X11-unix/X${DISPLAY_NUM}" ] && break
    sleep 0.25
  done
  KODI_ARGS+=("-fs")
fi

export HOME="${KODI_HOME}"
echo "Starting Kodi (profile ${KODI_HOME}, JSON-RPC :${PORT})..."
"$KODI_BIN" "${KODI_ARGS[@]}" &
KODI_PID=$!

cleanup() {
  kill "$KODI_PID" 2>/dev/null || true
  [ -n "${XVFB_PID:-}" ] && kill "$XVFB_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Kodi discovers a newly linked addon as disabled, whatever the database says,
# so enable it over JSON-RPC once the server is up.
echo "Waiting for JSON-RPC on :${PORT}..."
for _ in $(seq 1 90); do
  ping=$(curl -s -m 2 -X POST -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"JSONRPC.Ping"}' \
    "http://127.0.0.1:${PORT}/jsonrpc" 2>/dev/null || true)
  case "$ping" in *pong*) break ;; esac
  sleep 1
done

curl -s -m 10 -X POST -H 'Content-Type: application/json' \
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"Addons.SetAddonEnabled\",\"params\":{\"addonid\":\"${ADDON_ID}\",\"enabled\":true}}" \
  "http://127.0.0.1:${PORT}/jsonrpc" >/dev/null 2>&1 || true
echo "Addon ${ADDON_ID} enabled."
echo "Play a URL with:"
echo "  curl -s -X POST -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"Player.Open\",\"params\":{\"item\":{\"file\":\"plugin://${ADDON_ID}/?url=<encoded-url>\"}}}' http://127.0.0.1:${PORT}/jsonrpc"

wait "$KODI_PID"
