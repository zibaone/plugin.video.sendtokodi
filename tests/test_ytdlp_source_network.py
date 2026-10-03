"""Live tests against the real GitHub release endpoints.

These are opt-in (`pytest -m network`) because they hit the network and the
GitHub API. They exist to catch what mocks cannot: a wrong repository, a
renamed asset, or a nightly tag layout that the extractor chokes on.
"""

import os
import sys
import urllib.request

import pytest

from core import ytdlp_manager

pytestmark = pytest.mark.network

# Captured at import time, before conftest's autouse fixture replaces it.
_REAL_URLOPEN = urllib.request.urlopen


@pytest.fixture(autouse=True)
def _allow_network(monkeypatch):
    """Opt back into the network: conftest blocks urlopen for every test."""
    monkeypatch.setattr(urllib.request, "urlopen", _REAL_URLOPEN)


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(ytdlp_manager, "_addon_data_dir", lambda: str(tmp_path / "ytdlp"))


def test_nightly_latest_resolves_to_a_real_tag(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)

    latest = ytdlp_manager._resolve_latest_version(force_refresh=True, source="nightly")

    # Nightly tags carry a time component: YYYY.MM.DD.HHMMSS
    parts = latest.split(".")
    assert len(parts) == 4, latest
    assert all(p.isdigit() for p in parts), latest


def test_stable_latest_resolves_to_a_real_tag(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)

    latest = ytdlp_manager._resolve_latest_version(force_refresh=True, source="stable")

    parts = latest.split(".")
    assert len(parts) == 3, latest
    assert all(p.isdigit() for p in parts), latest


@pytest.mark.parametrize("source", ["stable", "nightly"])
def test_download_extract_and_import_installed_package(source, monkeypatch, tmp_path):
    """The full path: resolve -> download -> extract -> import the package."""
    _isolate(tmp_path, monkeypatch)

    latest = ytdlp_manager._resolve_latest_version(force_refresh=True, source=source)
    runtime_path = ytdlp_manager._download_and_install(latest, source=source)

    assert os.path.isfile(os.path.join(runtime_path, "yt_dlp", "__init__.py"))

    sys.path.insert(0, runtime_path)
    saved_modules = {k: v for k, v in sys.modules.items() if k.startswith("yt_dlp")}
    for key in saved_modules:
        del sys.modules[key]
    try:
        import yt_dlp

        assert yt_dlp.version.__version__ == latest, (yt_dlp.version.__version__, latest)
        # The exact symbols service.py uses.
        assert callable(yt_dlp.YoutubeDL)
        assert callable(yt_dlp.parse_options)
    finally:
        sys.path.remove(runtime_path)
        for key in [k for k in sys.modules if k.startswith("yt_dlp")]:
            del sys.modules[key]
        sys.modules.update(saved_modules)


def test_nightly_tags_are_listed_newest_first(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)

    versions = ytdlp_manager.list_available_versions(limit=5, source="nightly")

    assert versions, "nightly release list came back empty"
    assert versions == sorted(versions, key=lambda v: [int(p) for p in v.split(".")], reverse=True)


def test_channel_switch_changes_the_resolved_version(monkeypatch, tmp_path):
    """Same cache file, two sources: each must resolve its own latest."""
    _isolate(tmp_path, monkeypatch)

    stable = ytdlp_manager._resolve_latest_version(force_refresh=True, source="stable")
    nightly = ytdlp_manager._resolve_latest_version(force_refresh=True, source="nightly")

    # Switching back must not have been poisoned by the nightly lookup.
    assert ytdlp_manager._resolve_latest_version(source="stable") == stable
    assert ytdlp_manager._resolve_latest_version(source="nightly") == nightly
    assert stable != nightly
