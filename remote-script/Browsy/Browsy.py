"""
Browsy — Ableton Live Remote Script.

OSC ports:
  Receives on : 11000  (from Electron app)
  Sends to    : 11001  (to Electron app)

OSC addresses (in):
  /vst/scan          — scan all plugins, stream results back
  /vst/load  <name>  — load plugin by name (substring match)
  /vst/track/get     — get selected track name

OSC addresses (out):
  /vst/item  <name> <type>  — one plugin result (streamed during scan)
  /vst/scan/end             — scan complete
  /vst/load/ok              — load succeeded
  /vst/load/error  <msg>    — load failed
  /vst/track/name  <name>   — selected track name
"""

from _Framework.ControlSurface import ControlSurface
from .osc_server import OSCServer
from .browser import BrowserHelper

LISTEN_PORT = 11000
SEND_HOST   = '127.0.0.1'
SEND_PORT   = 11001


class Browsy(ControlSurface):
    def __init__(self, c_instance):
        super().__init__(c_instance)

        self._browser_helper = BrowserHelper(self.application().browser)

        handlers = {
            '/vst/scan':      self._on_scan,
            '/vst/load':      self._on_load,
            '/vst/track/get': self._on_track_get,
        }

        self._osc = OSCServer(LISTEN_PORT, handlers)
        self._osc.start()
        self.log_message('[Browsy] Started — listening on port {}'.format(LISTEN_PORT))

        try:
            self.song().view.add_selected_track_listener(self._on_selected_track_changed)
        except Exception as e:
            self.log_message('[Browsy] Track listener failed: {}'.format(e))

    def disconnect(self):
        try:
            self.song().view.remove_selected_track_listener(self._on_selected_track_changed)
        except Exception:
            pass
        self._osc.stop()
        self.log_message('[Browsy] Stopped')
        super().disconnect()

    def _on_selected_track_changed(self):
        self._do_track_get()

    # ── OSC handlers (called from OSC thread — schedule to main thread) ───────

    def _on_scan(self, args):
        self.schedule_message(0, self._do_scan)

    def _on_load(self, args):
        name = args[0] if args else ''
        self.schedule_message(0, lambda: self._do_load(name))

    def _on_track_get(self, args):
        self.schedule_message(0, self._do_track_get)

    # ── Main-thread actions ────────────────────────────────────────────────────

    def _do_scan(self):
        try:
            for name, type_tag, vendor, cat in self._browser_helper.scan_plugins():
                self._osc.send(SEND_HOST, SEND_PORT, '/vst/item', name, type_tag, vendor, cat)
            self._osc.send(SEND_HOST, SEND_PORT, '/vst/scan/end')
        except Exception as e:
            self.log_message('[Browsy] scan error: {}'.format(e))

    def _do_load(self, name):
        try:
            self._browser_helper.load_plugin(name)
            self._osc.send(SEND_HOST, SEND_PORT, '/vst/load/ok')
        except ValueError as e:
            self._osc.send(SEND_HOST, SEND_PORT, '/vst/load/error', str(e))
        except Exception as e:
            self._osc.send(SEND_HOST, SEND_PORT, '/vst/load/error', str(e))
            self.log_message('[Browsy] load error: {}'.format(e))

    def _do_track_get(self):
        try:
            song = self.song()
            track = song.view.selected_track
            name = track.name if track else ''
            self._osc.send(SEND_HOST, SEND_PORT, '/vst/track/name', name)
        except Exception as e:
            self.log_message('[Browsy] track_get error: {}'.format(e))
            self._osc.send(SEND_HOST, SEND_PORT, '/vst/track/name', '')
