"""
Standalone OSC test — no Ableton needed.
Sends test messages to the Electron app (port 11001) and listens for replies.

Usage:
  python test_osc.py [command]

Commands:
  scan       — request plugin scan
  load <n>   — request load plugin by name
  track      — request selected track name
  listen     — just listen for incoming messages (no send)

Default (no args): sends /vst/scan
"""

import sys
import time

# Reuse the OSCServer from the remote script
sys.path.insert(0, '.')
from VSTBrowser.osc_server import OSCServer

ELECTRON_HOST = '127.0.0.1'
ELECTRON_PORT = 11001   # Electron listens here
LISTEN_PORT   = 11000   # We listen here (same as M4L remote script)


def main():
    cmd  = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    arg2 = sys.argv[2] if len(sys.argv) > 2 else ''

    received = []

    def on_any(address):
        def handler(args):
            print('[IN] {} {}'.format(address, args))
            received.append((address, args))
        return handler

    handlers = {
        '/vst/item':       on_any('/vst/item'),
        '/vst/scan/end':   on_any('/vst/scan/end'),
        '/vst/load/ok':    on_any('/vst/load/ok'),
        '/vst/load/error': on_any('/vst/load/error'),
        '/vst/track/name': on_any('/vst/track/name'),
    }

    server = OSCServer(LISTEN_PORT, handlers)
    server.start()
    print('[test_osc] Listening on port {} …'.format(LISTEN_PORT))

    if cmd == 'scan':
        print('[OUT] /vst/scan')
        server.send(ELECTRON_HOST, ELECTRON_PORT, '/vst/scan')
        time.sleep(5)

    elif cmd == 'load':
        print('[OUT] /vst/load', arg2)
        server.send(ELECTRON_HOST, ELECTRON_PORT, '/vst/load', arg2)
        time.sleep(2)

    elif cmd == 'track':
        print('[OUT] /vst/track/get')
        server.send(ELECTRON_HOST, ELECTRON_PORT, '/vst/track/get')
        time.sleep(2)

    elif cmd == 'listen':
        print('[test_osc] Listening only — Ctrl+C to stop')
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    server.stop()
    print('[test_osc] Done. {} messages received.'.format(len(received)))


if __name__ == '__main__':
    main()
