"""
BrowserHelper — wraps Live's browser API for plugin scanning and loading.
"""

import csv
import glob
import gzip
import json
import os
import plistlib


def _amxd_cat(path):
    """Read an .amxd file and return 'audio-fx', 'midi-fx', 'instruments', or None."""
    try:
        try:
            with gzip.open(path, 'rb') as f:
                data = json.loads(f.read().decode('utf-8', errors='replace'))
        except Exception:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                data = json.load(f)
        ns = data.get('patcher', {}).get('classnamespace', '').lower()
        if 'instrument' in ns:
            return 'instruments'
        if 'midi' in ns:
            return 'midi-fx'
        if 'effect' in ns or 'dsp' in ns:
            return 'audio-fx'
    except Exception:
        pass
    return None


class BrowserHelper:
    def __init__(self, browser):
        self._browser = browser

    # ── Public ───────────────────────────────────────────────────────────────

    def scan_plugins(self):
        """
        Yield (name, type_tag, vendor, cat).
        - Ableton native: browser.instruments / audio_effects / midi_effects
        - VST3 / VST2:    read directly from PluginScanDb.txt (name+vendor+type in one place)
        - AUv2:           read from each .component Info.plist
        JS deduplicates by name, keeping the best format (VST3 > VST2 > AU).
        """
        # ── Ableton native devices ────────────────────────────────────────────
        for item in self._iter_browser_items(self._browser.instruments):
            yield item[0], 'instrument', 'Ableton', 'instruments'

        for item in self._iter_browser_items(self._browser.audio_effects):
            yield item[0], 'audio_effect', 'Ableton', 'audio-fx'

        for item in self._iter_browser_items(self._browser.midi_effects):
            yield item[0], 'midi_effect', 'Ableton', 'midi-fx'

        # browser.plugins tree skipped — Live's URIs use query:Plugins#VST3:Vendor:Name
        # format which carries no category info, so all entries would be dropped.
        # VST3/VST2 are covered by PluginScanDb.txt below; AU by plist scan at the end.

        # ── VST3 / VST2 from PluginScanDb.txt ────────────────────────────────
        prefs = os.path.expanduser('~/Library/Preferences/Ableton')
        db_files = sorted(glob.glob(os.path.join(prefs, 'Live *', 'PluginScanDb.txt')), key=os.path.getmtime)
        if db_files:
            try:
                with open(db_files[-1], 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if 'device:' not in line:
                            continue
                        try:
                            parts = next(csv.reader([line.strip()]))
                            if len(parts) < 5:
                                continue
                            uri, name, vendor = parts[2], parts[3], parts[4]
                            if ':audiofx:' in uri:
                                cat = 'audio-fx'
                            elif ':midifx:' in uri:
                                cat = 'midi-fx'
                            elif ':instr:' in uri:
                                cat = 'instruments'
                            else:
                                continue
                            if 'device:vst3:' in uri:
                                fmt = 'vst3'
                            elif 'device:vst:' in uri:
                                fmt = 'vst2'
                            else:
                                continue
                            yield name, fmt, vendor, cat
                        except Exception:
                            pass
            except Exception:
                pass

        # ── M4L devices from configured paths ────────────────────────────────
        import platform
        if platform.system() == 'Darwin':
            _cfg_path = os.path.expanduser(
                '~/Library/Application Support/Browsy/vst_browser_config.json'
            )
        else:
            _cfg_path = os.path.expanduser(
                '~/.config/Browsy/vst_browser_config.json'
            )
        try:
            with open(_cfg_path, 'r', encoding='utf-8') as _f:
                _cfg = json.load(_f)
        except Exception:
            _cfg = {}

        _m4l_vendor_mode = _cfg.get('m4l_vendor', 'blank')  # 'parent' or 'blank'
        for _m4l_root in _cfg.get('m4l_paths', []):
            _m4l_root = os.path.expanduser(_m4l_root)
            try:
                for dirpath, dirs, files in os.walk(_m4l_root):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for f in files:
                        if not f.endswith('.amxd') or f.startswith('.'):
                            continue
                        if _m4l_vendor_mode == 'parent':
                            vendor = os.path.basename(dirpath)
                        else:
                            vendor = ''
                        cat = _amxd_cat(os.path.join(dirpath, f)) or 'm4l'
                        yield os.path.splitext(f)[0], 'm4l', vendor, cat
            except Exception:
                pass

        # ── AUv2 from component Info.plist ───────────────────────────────────
        au_dirs = [
            '/Library/Audio/Plug-Ins/Components',
            os.path.expanduser('~/Library/Audio/Plug-Ins/Components'),
        ]
        for d in au_dirs:
            for component in glob.glob(os.path.join(d, '*.component')):
                plist_path = os.path.join(component, 'Contents', 'Info.plist')
                if not os.path.exists(plist_path):
                    continue
                try:
                    with open(plist_path, 'rb') as f:
                        data = plistlib.load(f)
                    for c in data.get('AudioComponents', []):
                        au_type = c.get('type', '')
                        raw = c.get('name', '')
                        if ': ' in raw:
                            vendor, name = raw.split(': ', 1)
                        else:
                            vendor, name = '', raw
                        if not name or vendor.lower() == 'apple':
                            continue
                        if au_type in ('aumu', 'augn'):
                            cat = 'instruments'
                        elif au_type in ('aufx', 'aumf'):
                            cat = 'audio-fx'
                        else:
                            continue
                        yield name, 'au', vendor, cat
                except Exception:
                    pass

    def load_plugin(self, name):
        """
        Find a plugin by name and load it.
        Tries exact match first, then substring, across all browser folders.
        """
        target = name.lower()

        all_children = []
        for attr in ['instruments', 'audio_effects', 'midi_effects', 'plugins']:
            try:
                all_children.append(getattr(self._browser, attr).children)
            except Exception:
                pass
        try:
            for place in self._browser.user_folders:
                if place.name == 'Devices':
                    all_children.append(place.children)
                    break
        except Exception:
            pass

        # Pass 1: exact match
        for children in all_children:
            item = self._find_in_items(children, target, exact=True)
            if item is not None:
                self._browser.load_item(item)
                return True

        # Pass 2: substring match
        for children in all_children:
            item = self._find_in_items(children, target, exact=False)
            if item is not None:
                self._browser.load_item(item)
                return True

        raise ValueError('Plugin not found: {}'.format(name))

    # ── Private ───────────────────────────────────────────────────────────────

    def _iter_browser_items(self, folder):
        """Recursively yield (name, item) from a browser folder."""
        try:
            for child in folder.children:
                if child.is_folder:
                    for sub in self._iter_browser_items(child):
                        yield sub
                else:
                    yield child.name, child
        except Exception:
            pass

    def _find_in_items(self, children, target, exact=False):
        """Depth-first search. exact=True matches full name, False matches substring."""
        try:
            for child in children:
                if child.is_folder:
                    result = self._find_in_items(child.children, target, exact)
                    if result is not None:
                        return result
                else:
                    n = child.name.lower()
                    if exact and n == target:
                        return child
                    elif not exact and target in n:
                        return child
        except Exception:
            pass
        return None
