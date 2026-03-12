"""
OSC server/client — pure Python stdlib, no external dependencies.
Implements OSC 1.0 encoding/decoding over UDP.
"""

import socket
import struct
import threading


class OSCServer:
    def __init__(self, port, handlers):
        """
        port     : UDP port to listen on
        handlers : dict { '/address': callable(args_list) }
        """
        self._port = port
        self._handlers = handlers
        self._socket = None
        self._thread = None
        self._running = False

    def start(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(('127.0.0.1', self._port))
        self._socket.settimeout(1.0)
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass

    def send(self, host, port, address, *args):
        try:
            data = self._encode_message(address, *args)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(data, (host, port))
            sock.close()
        except Exception:
            pass

    # ── Private ──────────────────────────────────────────────────────────────

    def _listen(self):
        while self._running:
            try:
                data, _ = self._socket.recvfrom(65535)
                self._dispatch(data)
            except socket.timeout:
                continue
            except Exception:
                pass

    def _dispatch(self, data):
        try:
            address, idx = self._read_string(data, 0)
            args = self._parse_args(data, idx)
            handler = self._handlers.get(address)
            if handler:
                handler(args)
        except Exception:
            pass

    def _parse_args(self, data, idx):
        if idx >= len(data):
            return []

        # Type tag string starts with ','
        if data[idx:idx + 1] != b',':
            return []

        type_str, idx = self._read_string(data, idx)
        tags = type_str[1:]  # strip leading ','

        args = []
        for tag in tags:
            if tag == 's':
                s, idx = self._read_string(data, idx)
                args.append(s)
            elif tag == 'i':
                if idx + 4 > len(data):
                    break
                val = struct.unpack_from('>i', data, idx)[0]
                idx += 4
                args.append(val)
            elif tag == 'f':
                if idx + 4 > len(data):
                    break
                val = struct.unpack_from('>f', data, idx)[0]
                idx += 4
                args.append(val)
            # skip unknown tags (no data consumed for 'N', 'T', 'F', etc.)

        return args

    def _read_string(self, data, offset):
        """Read a null-terminated, 4-byte-padded OSC string."""
        try:
            end = data.index(b'\x00', offset)
        except ValueError:
            return data[offset:].decode('utf-8', errors='replace'), len(data)

        s = data[offset:end].decode('utf-8', errors='replace')
        # Advance to next 4-byte boundary after the null terminator
        padded = end + 1
        remainder = padded % 4
        if remainder != 0:
            padded += 4 - remainder
        return s, padded

    # ── Encoding ─────────────────────────────────────────────────────────────

    def _encode_message(self, address, *args):
        data = self._encode_string(address)

        tags = ','
        encoded_args = b''
        for arg in args:
            if isinstance(arg, str):
                tags += 's'
                encoded_args += self._encode_string(arg)
            elif isinstance(arg, bool):
                # bool before int (bool is subclass of int in Python)
                tags += 'T' if arg else 'F'
            elif isinstance(arg, int):
                tags += 'i'
                encoded_args += struct.pack('>i', arg)
            elif isinstance(arg, float):
                tags += 'f'
                encoded_args += struct.pack('>f', arg)

        data += self._encode_string(tags)
        data += encoded_args
        return data

    def _encode_string(self, s):
        """Encode string as null-terminated, padded to 4 bytes."""
        b = s.encode('utf-8') + b'\x00'
        pad = (4 - len(b) % 4) % 4
        return b + b'\x00' * pad
