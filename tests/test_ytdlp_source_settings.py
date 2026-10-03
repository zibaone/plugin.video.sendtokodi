"""Integration test of the ytdlp_source setting, without running Kodi.

The unit tests in test_addon_params.py call resolve_ytdlp_source() with a
hand-made get_setting. This goes one step further and checks the pieces Kodi
actually reads: the setting must be declared in resources/settings.xml, its
labels must exist in strings.po, and the value Kodi persists in
addon_data/<addon>/settings.xml must resolve correctly.
"""

import os
import xml.etree.ElementTree as ET

import pytest

from core.addon_params import (
    DEFAULT_YTDLP_SOURCE,
    YTDLP_SOURCES,
    resolve_ytdlp_source,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_XML = os.path.join(REPO, "resources", "settings.xml")
STRINGS_PO = os.path.join(
    REPO, "resources", "language", "resource.language.en_gb", "strings.po"
)


def _find_setting(setting_id):
    root = ET.parse(SETTINGS_XML).getroot()
    for setting in root.iter("setting"):
        if setting.get("id") == setting_id:
            return setting
    return None


def test_setting_is_declared_in_settings_xml():
    setting = _find_setting("ytdlp_source")
    assert setting is not None, "ytdlp_source is missing from resources/settings.xml"
    assert setting.get("type") == "string"
    assert setting.get("label"), "the setting has no label id"


def test_setting_defaults_to_stable():
    setting = _find_setting("ytdlp_source")
    default = setting.find("default")
    assert default is not None, "ytdlp_source has no <default>"
    assert default.text == DEFAULT_YTDLP_SOURCE


def test_setting_offers_exactly_the_known_sources():
    setting = _find_setting("ytdlp_source")
    options = setting.findall("constraints/options/option")

    values = [o.text for o in options]
    assert values == list(YTDLP_SOURCES), values

    # Every option must have a label, otherwise Kodi shows an empty row.
    for option in options:
        assert option.get("label"), "option %r has no label" % option.text


def test_setting_uses_a_spinner_control():
    setting = _find_setting("ytdlp_source")
    control = setting.find("control")
    assert control is not None, "no <control> for ytdlp_source"
    assert control.get("type") == "spinner"


def test_setting_labels_exist_in_strings_po():
    """A missing string id renders as a raw number in the Kodi UI."""
    with open(STRINGS_PO, encoding="utf-8") as handle:
        content = handle.read()

    label_ids = {_find_setting("ytdlp_source").get("label")}
    for option in _find_setting("ytdlp_source").findall("constraints/options/option"):
        label_ids.add(option.get("label"))

    for label_id in label_ids:
        assert '"#%s"' % label_id in content, "string #%s is not in strings.po" % label_id


@pytest.mark.parametrize("value", YTDLP_SOURCES)
def test_value_persisted_by_kodi_resolves(value, tmp_path):
    """Reproduce the settings.xml Kodi writes into addon_data/."""
    addon_data = tmp_path / "plugin.video.sendtokodi"
    addon_data.mkdir()
    settings_file = addon_data / "settings.xml"
    settings_file.write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<settings version="2">\n'
        '    <setting id="ytdlp_autodownload">true</setting>\n'
        '    <setting id="ytdlp_source">%s</setting>\n'
        "</settings>\n" % value
    )

    persisted = {
        s.get("id"): (s.text or "")
        for s in ET.parse(str(settings_file)).getroot().iter("setting")
    }
    assert resolve_ytdlp_source(1, lambda _h, name: persisted.get(name, "")) == value


def test_unknown_persisted_value_falls_back_to_default(tmp_path):
    """A stale or hand-edited value must not break the addon."""
    assert resolve_ytdlp_source(1, lambda _h, _n: "sometrash") == DEFAULT_YTDLP_SOURCE
    assert resolve_ytdlp_source(1, lambda _h, _n: "") == DEFAULT_YTDLP_SOURCE
    assert resolve_ytdlp_source(1, lambda _h, _n: None) == DEFAULT_YTDLP_SOURCE


def test_persisted_value_is_normalized():
    """Kodi settings are user-editable; casing and blanks must not matter."""
    assert resolve_ytdlp_source(1, lambda _h, _n: "NIGHTLY") == "nightly"
    assert resolve_ytdlp_source(1, lambda _h, _n: "  stable  ") == "stable"
