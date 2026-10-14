"""Account emitted Ethernet frames once, before receiver-side IFB reinjection."""
import json
import re
import struct

def start(vm):
    vm.run(["bash","-c",
        "tcpdump --immediate-mode -i bench-client -Q out -s 0 -B 16384 -U -w /root/bench-output/client.pcap >/root/bench-output/client-capture.log 2>&1 & echo $! >/run/bench/client-capture.pid"],hide=True)
    vm.run(["bash","-c",
        "ip netns exec bench-origin tcpdump --immediate-mode -i bench-server -Q out -s 0 -B 16384 -U -w /root/bench-output/server.pcap >/root/bench-output/server-capture.log 2>&1 & echo $! >/run/bench/server-capture.pid"],hide=True)
    vm.run(["bash","-c",
        "for n in $(seq 1 50); do if grep -q 'listening on' /root/bench-output/client-capture.log && grep -q 'listening on' /root/bench-output/server-capture.log; then exit 0; fi; sleep 0.1; done; exit 1"],hide=True)

def stop(vm, directory):
    vm.run(["bash","-c",
        "kill -INT $(cat /run/bench/client-capture.pid) $(cat /run/bench/server-capture.pid); for n in $(seq 1 50); do if grep -q 'packets dropped by kernel' /root/bench-output/client-capture.log && grep -q 'packets dropped by kernel' /root/bench-output/server-capture.log; then exit 0; fi; sleep 0.1; done; exit 1"],hide=True)
    for peer in ("client","server"):
        log = vm.run(["cat","/root/bench-output/"+peer+"-capture.log"],hide=True).stdout
        (directory / (peer+"-capture.log")).write_text(log)
        assert re.search(r"^0 packets dropped by kernel$",log,re.MULTILINE), log
        vm._conn.get(remote="/root/bench-output/"+peer+".pcap",local=str(directory / (peer+".pcap")))

def inspect(filename, peer, port):
    source_mac = bytes.fromhex("525400ca0001" if peer=="client" else "525400ca0002")
    source_ip,destination_ip = (bytes((10,0,3,15)),bytes((10,0,3,2))) if peer=="client" else (bytes((10,0,3,2)),bytes((10,0,3,15)))
    totals = dict(frame_bytes=0,packets=0,arp_packets=0,tcp_packets=0)
    syns = set()
    with filename.open("rb") as stream:
        header = stream.read(24)
        assert header[:4] == b"\xd4\xc3\xb2\xa1" and struct.unpack("<I",header[20:24])[0] == 1, header
        while record := stream.read(16):
            assert len(record)==16
            _,_,saved,original = struct.unpack("<IIII",record)
            assert saved==original
            frame = stream.read(saved)
            assert len(frame)==saved and frame[6:12]==source_mac, (peer,frame[:14])
            totals["frame_bytes"] += saved
            totals["packets"] += 1
            kind = frame[12:14]
            if kind == b"\x08\x06":
                totals["arp_packets"] += 1
                continue
            assert kind == b"\x08\x00", kind
            ip = frame[14:]
            assert ip[0]>>4==4 and ip[9]==6
            assert ip[12:16]==source_ip and ip[16:20]==destination_ip
            assert (int.from_bytes(ip[6:8],"big") & 0x3fff)==0
            assert int.from_bytes(ip[2:4],"big")+14==saved
            tcp = ip[(ip[0]&15)*4:]
            first,last = struct.unpack(">HH",tcp[:4])
            assert port==(last if peer=="client" else first), (first,last,port)
            totals["tcp_packets"] += 1
            if tcp[13]&2:
                syns.add((first,last,int.from_bytes(tcp[4:8],"big")))
    totals["connections"] = len(syns)
    return totals

def validate(directory,before,after,port):
    capture = {peer:inspect(directory / (peer+".pcap"),peer,port) for peer in ("client","server")}
    delta = {peer:{direction:{key:after[peer][direction][key]-before[peer][direction][key]
        for key in after[peer][direction]} for direction in ("rx","tx")} for peer in ("client","server")}
    for peer in ("client","server"):
        assert capture[peer]["frame_bytes"]==delta[peer]["tx"]["bytes"], (peer,capture,delta)
        assert capture[peer]["packets"]==delta[peer]["tx"]["packets"], (peer,capture,delta)
        other = "server" if peer=="client" else "client"
        assert capture[other]["frame_bytes"]==delta[peer]["rx"]["bytes"], (peer,capture,delta)
        assert capture[other]["packets"]==delta[peer]["rx"]["packets"], (peer,capture,delta)
        assert delta[peer]["rx"]["dropped"]==delta[peer]["tx"]["dropped"]==0, delta
    (directory / "capture-accounting.json").write_text(json.dumps(dict(capture=capture,delta=delta),indent=2))
    return dict(link_download_bytes=capture["server"]["frame_bytes"],
        link_upload_bytes=capture["client"]["frame_bytes"],
        link_total_bytes=capture["server"]["frame_bytes"]+capture["client"]["frame_bytes"],
        connections=capture["client"]["connections"])
