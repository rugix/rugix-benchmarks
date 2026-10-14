"""Regression coverage for native-capture accounting edge cases."""
import struct
import tempfile
import unittest
from pathlib import Path

from rugix_benchmarks import capture, wire


class WireAccountingTests(unittest.TestCase):
    def test_partial_keepalive_response_and_retransmission(self):
        """Count only delivered bodies across keepalive, reordering and duplicate segments."""
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            response = (b"HTTP/1.1 206 Partial Content\r\nContent-Length: 3\r\n\r\nabc"
                        b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\nwxyz")
            client = [_frame("client", 50000, 80, 100, 2)]
            server = [_frame("server", 80, 50000, 200, 18),
                      _frame("server", 80, 50000, 231, 16, response[30:]),
                      _frame("server", 80, 50000, 201, 16, response[:30]),
                      _frame("server", 80, 50000, 201, 16, response[:30])]
            _pcap(directory / "client.pcap", client)
            _pcap(directory / "server.pcap", server)
            result = wire.summarize(directory, plaintext=True)
            self.assertEqual(result["http_body_bytes"], 7)
            self.assertEqual(result["http_responses"], 2)
            self.assertEqual(result["partial_http_responses"], 1)
            self.assertEqual(result["retransmitted_tcp_payload_bytes"], 30)

    def test_reused_port_and_sequence_wrap(self):
        """Keep independent connections distinct when an ephemeral port is reused."""
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"
            client, server = [], []
            for initial in (2**32 - 5, 900):
                client.append(_frame("client", 50000, 80, initial, 2))
                server += [_frame("server", 80, 50000, initial, 18),
                           _frame("server", 80, 50000, (initial + 1) % 2**32, 16, response)]
            _pcap(directory / "client.pcap", client)
            _pcap(directory / "server.pcap", server)
            result = wire.summarize(directory, plaintext=True)
            self.assertEqual(result["http_body_bytes"], 4)
            self.assertEqual(result["http_responses"], 2)
            self.assertEqual(result["partial_http_responses"], 0)
            self.assertEqual(capture.inspect(directory / "client.pcap", "client", 80)["connections"], 2)


def _frame(peer, source_port, destination_port, sequence, flags, payload=b""):
    source_mac = bytes.fromhex("525400ca0001" if peer == "client" else "525400ca0002")
    destination_mac = bytes.fromhex("525400ca0002" if peer == "client" else "525400ca0001")
    source_ip, destination_ip = (bytes((10, 0, 3, 15)), bytes((10, 0, 3, 2))) if peer == "client" else (bytes((10, 0, 3, 2)), bytes((10, 0, 3, 15)))
    ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 40 + len(payload), 0, 0, 64, 6, 0, source_ip, destination_ip)
    tcp = struct.pack(">HHIIBBHHH", source_port, destination_port, sequence, 0, 5 << 4, flags, 65535, 0, 0)
    return destination_mac + source_mac + b"\x08\x00" + ip + tcp + payload


def _pcap(path, frames):
    with path.open("wb") as output:
        output.write(struct.pack("<IHHIIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))
        for frame in frames:
            output.write(struct.pack("<IIII", 0, 0, len(frame), len(frame)))
            output.write(frame)


if __name__ == "__main__":
    unittest.main()
