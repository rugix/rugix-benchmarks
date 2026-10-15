"""Run verified native installs in fresh guests with balanced candidate order."""
from __future__ import annotations

import json
import os
import random
import re
import shlex
import subprocess
import sys
from pathlib import Path

from rugix_testkit import VMHandle

from . import capture, network, wire
from .common import CACHE, ROOT, bundle_key, digest, fingerprint_paths, read_json, save_json, tools, updater_path
from .fixtures import configure_slots, start_rauc
from .images import image_path
from .models.benchmark import Sample
from .vm import config

def run_sample(plan,plan_hash,workload,candidate,rtt,repetition,output):
    name = f"{workload.id}-rtt{rtt}-{candidate.id}-{repetition}"
    directory = output / "runs" / name
    if directory.exists():
        raise ValueError("Run directory already exists; preserve failed evidence before repeating: "+str(directory))
    bundle_directory = CACHE / "bundles" / workload.target.id / bundle_key(candidate)
    bundle = read_json(bundle_directory / "bundle.json")
    updater = candidate.updater
    binary = updater_path(candidate)
    expected_binary = digest(Path(binary))
    protocol = "HTTP/1.1"
    port,scheme = 8080,"http"
    if updater.tag=="Rauc" and updater.tls:
        scheme = "https"
        port = 8444 if updater.protocol.tag=="Http2" else 8443
        protocol = "HTTP/2.0" if updater.protocol.tag=="Http2" else "HTTP/1.1"
    print("START "+name,flush=True)
    with VMHandle.start(config(plan,workload.id),work_dir=directory,
                        private_key=CACHE / "keys/id_rsa",boot_timeout=180) as vm:
        configure_slots(vm)
        checked = vm.run(["sha256sum",binary],hide=True).stdout.split()[0]
        if checked!=expected_binary:
            raise RuntimeError("Native updater binary changed")
        network.configure(vm,plan,workload,candidate,rtt,directory)
        network.calibrate(vm,plan,rtt,directory)
        served_sha = vm.run(["sha256sum", "/srv/bench/" + bundle["filename"]], hide=True, timeout=300).stdout.split()[0]
        if served_sha != bundle["sha256"]:
            raise RuntimeError("Prepared fixture serves a different bundle")
        if updater.tag=="Rauc":
            status = start_rauc(vm)
            command = [binary,"install"]
            if updater.tls:
                command.append("--tls-ca=/etc/nginx/bench.crt")
        else:
            status = vm.run_json([binary,"system","info"])
            if status["boot"]["activeGroup"]!="a":
                raise RuntimeError("Unexpected active Rugix group")
            command = [binary,"update","install","--reboot","no",
                       "--bundle-hash",bundle["trusted_hash"]]
        save_json(directory / "status-before.json",status)
        source_size = image_path(workload.source.id).stat().st_size
        warm = (
            "set -euo pipefail; sync; echo 3 >/proc/sys/vm/drop_caches; "
            f"head -c {source_size} /dev/vdb1 >/dev/null; "
            "cat /srv/bench/"+bundle["filename"]+" >/dev/null; "
            "find /run/rugix/mounts/data/rugix/slots /root/rauc-corpus-data -type f -exec cat {} + >/dev/null; "
            ": >/root/bench-output/nginx-access.jsonl"
        )
        warmed = vm.run(["bash","-x","-c",warm],hide=True,check=False,timeout=300)
        (directory / "cache-warmup.log").write_text(warmed.stdout + warmed.stderr)
        if not warmed.ok:
            raise RuntimeError("Cache warmup failed: " + warmed.stderr)
        source_sha = vm.run(["sh","-c",f"head -c {source_size} /dev/vdb1 | sha256sum"],hide=True,timeout=300).stdout.split()[0]
        if source_sha!=digest(image_path(workload.source.id)):
            raise RuntimeError("Source slot differs from the selected corpus image")
        (directory / "memory-before.log").write_text(vm.run(["cat","/proc/meminfo"],hide=True).stdout)
        isolate = network.settle(vm)
        vm.run(["head","-c","1048576","/dev/zero"],hide=True)
        if network.settle(vm)!=isolate:
            raise RuntimeError("Management traffic leaked into benchmark link")
        before = network.settle(vm)
        qdisc_before = network.qdiscs(vm)
        capture.start(vm)
        url = f"{scheme}://10.0.3.2:{port}/{bundle['filename']}"
        wrapper = (
            "TIMEFORMAT='ELAPSED %R %U %S'; { time "+
            shlex.join(command+[url])+
            " >/root/install.log 2>&1; } 2>/root/install.time; status=$?; cat /root/install.time; exit $status"
        )
        installed = vm.run(["bash","-c",wrapper],check=False,hide=True,timeout=7200)
        after = network.settle(vm)
        qdisc_after = network.qdiscs(vm)
        save_json(directory / "raw-counters.json",dict(before=before,after=after,
                  qdisc_before=qdisc_before,qdisc_after=qdisc_after))
        capture.stop(vm,directory)
        log = vm.run(["cat","/root/install.log"],hide=True).stdout
        (directory / "install.log").write_text(log)
        (directory / "timing.log").write_text(installed.stdout+installed.stderr)
        access = vm.run(["cat","/root/bench-output/nginx-access.jsonl"],hide=True).stdout
        (directory / "nginx-access.jsonl").write_text(access)
        (directory / "nginx-error.log").write_text(vm.run(["cat","/root/bench-output/nginx-error.log"],hide=True).stdout)
        native = ""
        if updater.tag=="Rauc":
            native = vm.run(["journalctl","-u","rauc-benchmark","--no-pager"],hide=True).stdout
            (directory / "service.log").write_text(native)
        if not installed.ok:
            raise RuntimeError(name+" failed:\n"+log[-5000:])
        elapsed = re.search(r"ELAPSED ([0-9.]+)",installed.stdout)
        if elapsed is None:
            raise RuntimeError("Missing native timing")
        payload = bundle["payload"]
        actual = vm.run(["sh","-c",f"head -c {payload['bytes']} /dev/vdb2 | sha256sum"],
                        hide=True,timeout=300).stdout.split()[0]
        if actual!=payload["sha256"]:
            raise RuntimeError("Installed target digest differs")
        traffic = capture.validate(directory,before,after,port)
        for peer in ("client","server"):
            old = {row["handle"]:row for row in qdisc_before[peer]}
            for row in qdisc_after[peer]:
                if row["drops"]!=old[row["handle"]]["drops"] or row["backlog"] or row["qlen"]:
                    raise RuntimeError("Queue drop or unfinished packet delivery")
        requests = [json.loads(line) for line in access.splitlines()]
        if not requests or any(row["method"]!="GET" or row["uri"]!="/"+bundle["filename"] for row in requests):
            raise RuntimeError("Unexpected native HTTP request")
        if {row["protocol"] for row in requests}!={protocol}:
            raise RuntimeError("Native HTTP protocol does not match candidate")
        if any(row["status"] not in ("200","206") for row in requests):
            raise RuntimeError("Failed HTTP response")
        if scheme=="https" and any(row["tls"] not in ("TLSv1.2","TLSv1.3") for row in requests):
            raise RuntimeError("TLS was not negotiated")
        server_body_bytes = sum(int(row["body_bytes"]) for row in requests)
        packet_details = wire.summarize(directory,plaintext=scheme=="http")
        save_json(directory / "wire-accounting.json",packet_details)
        body_bytes = packet_details.get("http_body_bytes",server_body_bytes)
        if updater.tag=="Rauc" and body_bytes!=server_body_bytes:
            raise RuntimeError("Captured RAUC body differs from native/server body")
        if updater.tag=="Rauc":
            downloaded = re.search(r"nbd dl_size: count=(\d+) sum=(\d+)\.000",native)
            if not downloaded or int(downloaded[1])!=len(requests) or int(downloaded[2])!=body_bytes:
                raise RuntimeError("RAUC native download counters disagree with Nginx")
            if "request failed:" in native:
                raise RuntimeError("RAUC logged a request failure")
        connections = len({row["connection"] for row in requests})
        if traffic["connections"]!=connections:
            raise RuntimeError("Native/server connection counts differ")
        record = Sample(schema_version=1,workload=workload.id,candidate=candidate.id,
            repetition=repetition,rtt_ms=rtt,seconds=float(elapsed[1]),body_bytes=body_bytes,
            server_body_bytes=server_body_bytes,
            partial_http_responses=packet_details.get("partial_http_responses",0),
            retransmitted_tcp_payload_bytes=packet_details["retransmitted_tcp_payload_bytes"],
            download_bytes=traffic["link_download_bytes"],upload_bytes=traffic["link_upload_bytes"],
            requests=len(requests),connections=connections,payload_bytes=payload["bytes"],
            source_sha256=source_sha,payload_sha256=actual,
            bundle_bytes=bundle["bytes"],bundle_sha256=bundle["sha256"],
            updater_sha256=expected_binary,plan_sha256=plan_hash,
            run_directory=os.path.relpath(directory, ROOT))
        save_json(directory / "result.json",record)
        print("RESULT "+record.model_dump_json(by_alias=True),flush=True)
    for disk in ("drive0.qcow2","drive1.qcow2"):
        (directory / disk).unlink()
    return record

def campaign_inputs(plan):
    package = ROOT / "src/rugix_benchmarks"
    files = [package / (name + ".py") for name in ("common", "capture", "network", "wire", "runner", "fixtures", "images", "vm")]
    files += list((package / "models").rglob("*.py"))
    files += [path for path in (ROOT / "fixtures").rglob("*") if path.is_file()]
    files += [ROOT / "uv.lock", ROOT / "nix/flake.nix", ROOT / "nix/flake.lock"]
    files += list({CACHE / "theory" / workload.id / (bundle_key(candidate) + ".json") for workload in plan.workloads for candidate in plan.candidates})
    files += list({CACHE / "theory" / workload.target.id / "base.json" for workload in plan.workloads})
    fixtures = {workload.id: read_json(CACHE / "golden" / workload.id / "fixture.json") for workload in plan.workloads}
    bundles = {workload.target.id + "/" + bundle_key(candidate): read_json(CACHE / "bundles" / workload.target.id / bundle_key(candidate) / "bundle.json")
               for workload in plan.workloads for candidate in plan.candidates}
    return dict(files=fingerprint_paths(files), tools=tools(), fixtures=fixtures, bundles=bundles,
                python=sys.version, qemu=subprocess.check_output(["qemu-system-x86_64", "--version"], text=True),
                host_kernel=subprocess.check_output(["uname", "-a"], text=True),
                host_cpu={key.strip(): value.strip() for line in Path("/proc/cpuinfo").read_text().split("\n\n")[0].splitlines()
                          if ":" in line for key, value in [line.split(":", 1)]
                          if key.strip() in ("vendor_id", "cpu family", "model", "model name", "stepping", "microcode", "flags")})

def run(plan,plan_path,output,*,limit=None):
    output.mkdir(parents=True,exist_ok=True)
    plan_hash = digest(plan_path)
    manifest = output / "plan.json"
    if manifest.exists():
        if digest(manifest)!=plan_hash:
            raise ValueError("Campaign plan changed; use a new output directory")
    else:
        manifest.write_bytes(plan_path.read_bytes())
    provenance = output / "provenance.json"
    current = campaign_inputs(plan)
    if provenance.exists():
        if read_json(provenance) != current:
            raise ValueError("Campaign inputs or harness changed; use a new output directory")
    else:
        save_json(provenance, current)
    samples = output / "samples.json"
    report = read_json(samples) if samples.exists() else []
    durable = {}
    for result_path in sorted((output / "runs").glob("*/result.json")):
        record = Sample.model_validate_json(result_path.read_text()).model_dump(by_alias=True)
        identity = (record["workload"], record["candidate"], record["rtt_ms"], record["repetition"])
        if identity in durable:
            raise ValueError("Duplicate durable sample")
        durable[identity] = record
    for record in report:
        identity = (record["workload"], record["candidate"], record["rtt_ms"], record["repetition"])
        if durable.get(identity) != record:
            raise ValueError("Aggregate differs from durable sample evidence")
    if len(durable) != len(report):
        report = list(durable.values())
        save_json(samples, report)
    completed = {(row["workload"],row["candidate"],row["rtt_ms"],row["repetition"]) for row in report}
    allowed = {(workload.id, candidate.id, rtt, repetition) for workload in plan.workloads for candidate in plan.candidates for rtt in plan.rtt_ms for repetition in range(plan.repetitions)}
    if not completed.issubset(allowed) or len(completed)!=len(report) or any(row["plan_sha256"]!=plan_hash for row in report):
        raise ValueError("Existing campaign has duplicate or incompatible samples")
    blocks = [(workload,rtt) for workload in plan.workloads for rtt in plan.rtt_ms]
    generator = random.Random(plan.order_seed)
    orders = {}
    for workload,rtt in blocks:
        order = list(plan.candidates)
        generator.shuffle(order)
        orders[workload.id,rtt] = order
    count = 0
    for repetition in range(plan.repetitions):
        scheduled = list(blocks)
        generator.shuffle(scheduled)
        for workload,rtt in scheduled:
            order = orders[workload.id,rtt]
            offset = repetition%len(order)
            for candidate in order[offset:]+order[:offset]:
                identity = (workload.id,candidate.id,rtt,repetition)
                if identity in completed:
                    continue
                record = run_sample(plan,plan_hash,workload,candidate,rtt,repetition,output)
                report.append(record.model_dump(by_alias=True))
                save_json(samples,report)
                completed.add(identity)
                count += 1
                if limit is not None and count>=limit:
                    return report
    return report
