"""Native Nginx and receiver-ingress kernel network impairment."""
from __future__ import annotations

import re
import statistics
import time
from .common import ROOT, bundle_key, save_json, tools
from .fixtures import ASSETS

CLIENT = "bench-client"
SERVER = "bench-server"

def configure(vm, plan, workload, candidate, rtt, directory):
    runtime = tools()["runtime"]
    for name in ("nginx","iperf3","tcpdump","ethtool"):
        vm.run(["ln","-sf",runtime+"/bin/"+name,"/usr/local/bin/"+name],hide=True)
    vm.upload(ROOT / "fixtures/setup-network.sh","/root/setup-network.sh")
    setup = vm.run(["bash","-x","/root/setup-network.sh",str(rtt//2),str(plan.rate_bits_per_second)],
                   hide=True,check=False,timeout=30)
    (directory / "network-setup.log").write_text(setup.stdout+setup.stderr)
    if not setup.ok:
        raise RuntimeError(setup.stdout+setup.stderr)
    vm.run(["mkdir","-p","/run/bench","/root/bench-output","/srv/bench","/etc/nginx"],hide=True)
    vm.run(["mount","--bind",ASSETS+"/bundles/"+bundle_key(candidate),"/srv/bench"],hide=True)
    vm.run(["cp",ASSETS+"/tls/server.crt","/etc/nginx/bench.crt"],hide=True)
    vm.run(["cp",ASSETS+"/tls/server.key","/etc/nginx/bench.key"],hide=True)
    vm.run(["chmod","0644","/etc/nginx/bench.crt"],hide=True)
    vm.run(["chmod","0600","/etc/nginx/bench.key"],hide=True)
    vm.upload(ROOT / "fixtures/nginx.conf","/etc/nginx/bench.conf")
    vm.run(["ip","netns","exec","bench-origin","nginx","-t","-p","/run/bench/","-c","/etc/nginx/bench.conf"],hide=True)
    vm.run(["ip","netns","exec","bench-origin","nginx","-p","/run/bench/","-c","/etc/nginx/bench.conf"],hide=True)
    for peer,command in (("client",["ethtool","-k",CLIENT]),
                         ("server",["ip","netns","exec","bench-origin","ethtool","-k",SERVER])):
        (directory / ("offloads-"+peer+".log")).write_text(vm.run(command,hide=True).stdout)

def counters(vm):
    client = vm.run_json(["ip","-s","-j","link","show","dev",CLIENT])[0]["stats64"]
    server = vm.run_json(["ip","netns","exec","bench-origin","ip","-s","-j","link","show","dev",SERVER])[0]["stats64"]
    return dict(client=client,server=server)

def settle(vm):
    previous = counters(vm)
    for _ in range(30):
        time.sleep(0.2)
        current = counters(vm)
        if current==previous:
            return current
        previous = current
    raise RuntimeError("Benchmark link did not settle")

def qdiscs(vm):
    return dict(client=vm.run_json(["tc","-s","-j","qdisc","show","dev","bench-ifb"]),
                server=vm.run_json(["ip","netns","exec","bench-origin","tc","-s","-j","qdisc","show","dev","bench-ifb"]))

def calibrate(vm, plan, rtt, directory):
    vm.run(["ping","-n","-c","1","10.0.3.2"],hide=True)
    ping = vm.run(["ping","-n","-c","10","-i","0.1","10.0.3.2"],hide=True).stdout
    (directory / "ping.log").write_text(ping)
    replies = [float(value) for value in re.findall(r"time=([0-9.]+) ms",ping)]
    if len(replies)!=10 or min(replies)<rtt-1 or statistics.median(replies)>rtt+5:
        raise RuntimeError("RTT calibration failed:\n"+ping)
    vm.run(["ip","netns","exec","bench-origin","iperf3","-s","-D","-p","5201"],hide=True)
    test = vm.run_json(["iperf3","-c","10.0.3.2","-p","5201","-R","-P","4","-t","6","-O","5","-J"],timeout=30)
    save_json(directory / "iperf.json",test)
    vm.run(["ip","netns","exec","bench-origin","pkill","-x","iperf3"],hide=True)
    rate = test["end"]["sum_received"]["bits_per_second"]
    if not 0.85*plan.rate_bits_per_second<=rate<=1.02*plan.rate_bits_per_second:
        raise RuntimeError(f"Bandwidth calibration failed: {rate} bit/s")
    settle(vm)
    queues = qdiscs(vm)
    save_json(directory / "qdisc-calibration.json",queues)
    for peer in ("client","server"):
        kinds = {row["kind"]:row for row in queues[peer]}
        if kinds["tbf"]["options"]["rate"]!=plan.rate_bits_per_second//8:
            raise RuntimeError("Wrong TBF rate")
        value = kinds["netem"]["options"].get("delay",{})
        delay = value.get("delay",0.0) if isinstance(value,dict) else value
        if abs(delay-rtt/2000)>1e-9:
            raise RuntimeError("Wrong netem delay")
    summary = dict(rtt_minimum_ms=min(replies),rtt_median_ms=statistics.median(replies),
        rtt_average_ms=statistics.mean(replies),rtt_maximum_ms=max(replies),
        download_bits_per_second=rate)
    save_json(directory / "calibration.json",summary)
    return summary
