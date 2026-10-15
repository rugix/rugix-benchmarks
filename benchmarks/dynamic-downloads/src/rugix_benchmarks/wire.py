"""Separate unique TCP data, retransmissions and plaintext HTTP bodies."""
from __future__ import annotations

import struct
from collections import defaultdict

import h11

def summarize(directory, *, plaintext):
    stats = dict(ethernet_bytes=0,ip_bytes=0,tcp_bytes=0,arp_bytes=0,
                 tcp_payload_bytes=0,retransmitted_tcp_payload_bytes=0)
    streams = defaultdict(list)
    for peer in ("client","server"):
        active = {}
        with (directory / (peer+".pcap")).open("rb") as source:
            source.read(24)
            while header := source.read(16):
                _,_,size,_ = struct.unpack("<IIII",header)
                frame = source.read(size)
                if frame[12:14]==b"\x08\x06":
                    stats["arp_bytes"] += size
                    continue
                ip = frame[14:]
                ip_header = (ip[0]&15)*4
                tcp = ip[ip_header:int.from_bytes(ip[2:4],"big")]
                tcp_header = (tcp[12]>>4)*4
                stats["ethernet_bytes"] += 14
                stats["ip_bytes"] += ip_header
                stats["tcp_bytes"] += tcp_header
                ports = struct.unpack(">HH",tcp[:4])
                sequence = int.from_bytes(tcp[4:8],"big")
                if tcp[13]&2:
                    active[ports] = sequence
                if ports not in active:
                    raise ValueError("Capture missed a TCP handshake")
                payload = tcp[tcp_header:]
                stats["tcp_payload_bytes"] += len(payload)
                if payload:
                    base = active[ports]
                    offset = (sequence-base-1)%2**32
                    streams[peer,ports,base].append((offset,payload))
    unique = 0
    bodies = 0
    responses = 0
    partial = 0
    for (peer,_,_),segments in streams.items():
        end = 0
        parser = _HTTPBodies() if plaintext and peer=="server" else None
        for offset,payload in sorted(segments,key=lambda item:item[0]):
            if offset>end:
                raise ValueError("Gap in captured TCP sequence data")
            fresh = payload[max(0,end-offset):]
            if fresh:
                unique += len(fresh)
                end = offset+len(payload)
                if parser is not None:
                    parser.feed(fresh)
        if parser is not None:
            bodies += parser.body_bytes
            responses += parser.responses
            partial += int(parser.pending)
    stats["unique_tcp_payload_bytes"] = unique
    stats["retransmitted_tcp_payload_bytes"] = stats["tcp_payload_bytes"]-unique
    if plaintext:
        stats.update(http_body_bytes=bodies,http_responses=responses,
                     partial_http_responses=partial,http_headers_bytes=unique-bodies)
    return stats

class _HTTPBodies:
    """Use h11 framing while retaining bytes from intentionally closed responses."""
    def __init__(self):
        self.connection = h11.Connection(h11.CLIENT)
        self.body_bytes = 0
        self.responses = 0
        self.pending = False
        self._request()

    def _request(self):
        self.connection.send(h11.Request(method="GET",target="/",headers=[("Host","benchmark")]))
        self.connection.send(h11.EndOfMessage())

    def feed(self, payload):
        self.connection.receive_data(payload)
        while True:
            event = self.connection.next_event()
            if event is h11.NEED_DATA or event is h11.PAUSED:
                return
            if isinstance(event,h11.Response):
                if event.status_code not in (200,206):
                    raise ValueError("Unexpected captured HTTP status")
                self.responses += 1
                self.pending = True
            elif isinstance(event,h11.Data):
                self.body_bytes += len(event.data)
            elif isinstance(event,h11.EndOfMessage):
                self.pending = False
                if self.connection.our_state is h11.DONE and self.connection.their_state is h11.DONE:
                    self.connection.start_next_cycle()
                    self._request()
